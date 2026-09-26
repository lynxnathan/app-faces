from threading import Thread
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from .community import drain_outbox, endpoint, enqueue, preview
from .core import Resolver, data_dir, icon_path
from .i18n import t
from .ui import install_style


def run() -> int:
    app = Gtk.Application(
        application_id="io.github.appfaces.Onboarding", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    app.connect("activate", lambda app: Welcome(app).present())
    return int(app.run([]))


class Welcome(Gtk.ApplicationWindow):  # type: ignore[misc]
    def __init__(self, app: Any) -> None:
        super().__init__(
            application=app, title=t("Welcome to App Faces"), default_width=580, default_height=620
        )
        install_style(self)
        self.set_titlebar(Gtk.HeaderBar())
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
            margin_start=24,
            margin_end=24,
            margin_top=20,
            margin_bottom=20,
        )
        self.set_child(box)
        title = Gtk.Label(label=t("Application icons"), xalign=0)
        title.add_css_class("title-1")
        box.append(title)
        box.append(
            Gtk.Label(
                label=t(
                    "Recognized icons are applied automatically. Sharing selected names and icons is optional."
                ),
                wrap=True,
                xalign=0,
            )
        )
        box.append(
            Gtk.Label(
                label=t("No account, file paths or launch commands. You choose what to share."),
                wrap=True,
                xalign=0,
            )
        )
        self.rows: list[tuple[Any, dict[str, Any]]] = []
        listing = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        listing.add_css_class("boxed-list")
        for entry in Resolver().entries:
            asset = icon_path(entry["icon"])
            if not asset:
                continue
            row = Gtk.Box(spacing=12, margin_top=8, margin_bottom=8, margin_start=12, margin_end=12)
            check = Gtk.CheckButton()
            check.set_tooltip_text(t("Share {name}", name=entry["name"]))
            check.update_property(
                [Gtk.AccessibleProperty.LABEL], [t("Share {name}", name=entry["name"])]
            )
            icon = Gtk.Image.new_from_file(str(asset))
            icon.set_pixel_size(32)
            row.append(check)
            row.append(icon)
            row.append(Gtk.Label(label=entry["name"], xalign=0))
            listing.append(row)
            self.rows.append((check, dict(entry, asset=str(asset))))
        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(listing)
        box.append(scroll)
        self.status = Gtk.Label(
            label=t("Contributions stay private until approved."), wrap=True, xalign=0
        )
        box.append(self.status)
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        skip = Gtk.Button(label=t("Not now"))
        skip.connect("clicked", lambda *_: self.close())
        buttons.append(skip)
        self.share = Gtk.Button(label=t("Share selected"))
        self.share.add_css_class("suggested-action")
        self.share.connect("clicked", self.submit)
        buttons.append(self.share)
        box.append(buttons)
        try:
            endpoint()
        except ValueError:
            self.share.set_sensitive(False)
            self.status.set_text(t("Sharing is not configured. Automatic icons still work."))
        data_dir().mkdir(parents=True, exist_ok=True)
        (data_dir() / "onboarding-seen").touch()

    def submit(self, *_: Any) -> None:
        selected = [entry for check, entry in self.rows if check.get_active()]
        if not selected:
            self.status.set_text(t("Select icons to share, or choose Not now."))
            return
        self.share.set_sensitive(False)
        self.status.set_text(t("Preparing selected icons…"))

        def worker() -> None:
            try:
                for entry in selected:
                    payload = preview(
                        entry["id"].removesuffix(".desktop"),
                        entry["name"],
                        entry["asset"],
                        variant="installed",
                    )
                    enqueue(payload, consent=True)
                drain_outbox()
                GLib.idle_add(
                    self.status.set_text,
                    t(
                        "Icons queued for review: {count}. Offline uploads will be retried.",
                        count=len(selected),
                    ),
                )
            except Exception as exc:
                GLib.idle_add(self.status.set_text, str(exc))
            GLib.idle_add(self.share.set_sensitive, True)

        Thread(target=worker, daemon=True).start()
