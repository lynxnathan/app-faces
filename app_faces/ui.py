from pathlib import Path
from threading import Thread
from typing import Any, Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk

from .core import Resolver, application_search_name, fetch_icon, icon_path, sync_catalog
from .i18n import RTL_LANGUAGES, language, t
from .state import apply, refresh_warning, undo

CATALOG_REFRESH_SECONDS = 86_400


def install_style(widget: Any) -> None:
    widget.set_direction(
        Gtk.TextDirection.RTL if language() in RTL_LANGUAGES else Gtk.TextDirection.LTR
    )
    provider = Gtk.CssProvider()
    provider.load_from_string("""
      .app-faces { background: @theme_bg_color; }
      .app-faces .hero { padding: 24px; border-radius: 18px;
        background: alpha(@theme_selected_bg_color, .08); }
      .app-faces .hero image { margin: 8px 0; }
      .app-faces .eyebrow { font-size: 11px; font-weight: 700; letter-spacing: 1px;
        color: @theme_selected_bg_color; }
      .app-faces .title-1 { font-size: 25px; font-weight: 750; }
      .app-faces .section-title { font-weight: 650; }
      .app-faces .supporting { opacity: .72; font-size: 12px; }
      .app-faces .boxed-list { border: 1px solid alpha(currentColor, .12);
        border-radius: 12px; }
      .app-faces .boxed-list row { padding: 4px; }
      .app-faces button { padding: 9px 14px; border-radius: 9px; }
      .app-faces entry { min-height: 36px; border-radius: 8px; }
      .app-faces .status-bar { padding: 12px; border-radius: 10px;
        background: alpha(@theme_selected_bg_color, .07); }
    """)
    Gtk.StyleContext.add_provider_for_display(
        widget.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    widget.add_css_class("app-faces")


def label(text: str, css: str = "", **kwargs: Any) -> Any:
    item = Gtk.Label(label=text, xalign=0, wrap=True, **kwargs)
    if css:
        item.add_css_class(css)
    return item


def status_text(status: str) -> str:
    return {
        "pending": t("Pending"),
        "submitted": t("Submitted"),
        "approved": t("Published"),
        "correction": t("Correction requested"),
        "rejected": t("Rejected"),
        "merged": t("Merged"),
        "revoked": t("Revoked"),
        "withdrawn": t("Withdrawn"),
        "cancelled": t("Cancelled"),
        "failed": t("Upload failed"),
    }.get(status, status)


def run(path: Path) -> int:
    app = Gtk.Application(
        application_id="io.github.appfaces.Chooser", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    app.connect("activate", lambda application: Chooser(application, path).present())
    return int(app.run([]))


class Chooser(Gtk.ApplicationWindow):  # type: ignore[misc]
    def __init__(self, app: Any, path: Path) -> None:
        super().__init__(application=app, title="App Faces", default_width=620, default_height=820)
        install_style(self)
        self.closed = False
        self.connect("close-request", self.on_close)
        self.path = path.absolute()
        self.resolver = Resolver()
        self.selected = ""
        self.busy = False
        self.set_titlebar(Gtk.HeaderBar())
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
            margin_top=20,
            margin_bottom=20,
            margin_start=24,
            margin_end=24,
        )
        page = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        page.set_child(box)
        page.set_vexpand(True)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(page)
        self.set_child(outer)
        title = Gtk.Label(label=t("Application icon"), xalign=0)
        title.add_css_class("title-1")
        box.append(title)
        filename = Gtk.Label(label=self.path.name, xalign=0, selectable=True, ellipsize=3)
        filename.set_tooltip_text(str(self.path))
        box.append(filename)
        self.preview = Gtk.Image.new_from_icon_name("application-x-executable")
        self.preview.set_pixel_size(96)
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero.add_css_class("hero")
        eyebrow = Gtk.Label(label=t("Icon preview"))
        eyebrow.add_css_class("eyebrow")
        hero.append(eyebrow)
        hero.append(self.preview)
        box.append(hero)
        self.status = Gtk.Label(label=t("Finding an icon…"), wrap=True)
        self.status.add_css_class("status-bar")
        box.append(self.status)
        row = Gtk.Box(spacing=8)
        choose = self.choose_button = Gtk.Button(label=t("Choose image…"))
        choose.connect("clicked", self.choose_file)
        row.append(choose)
        box.append(row)
        self.search = Gtk.SearchEntry(placeholder_text=t("Search catalog…"), hexpand=True)
        self.search.update_property([Gtk.AccessibleProperty.LABEL], [t("Search catalog")])
        self.search.connect("search-changed", self.search_changed)
        box.append(self.search)
        self.results = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.results.add_css_class("boxed-list")
        empty = Gtk.Label(
            label=t("No icons found. Search again or choose an image."),
            wrap=True,
            margin_top=28,
            margin_bottom=28,
            margin_start=18,
            margin_end=18,
        )
        empty.add_css_class("dim-label")
        self.results.set_placeholder(empty)
        scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=130)
        scroll.set_child(self.results)
        box.append(scroll)
        self.credit = Gtk.Label(label=t("Changes take effect when you apply."), wrap=True, xalign=0)
        self.credit.add_css_class("dim-label")
        box.append(self.credit)
        actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        self.restore = Gtk.Button(label=t("Restore previous"))
        self.restore.connect("clicked", self.undo)
        actions.append(self.restore)
        self.apply_button = Gtk.Button(label=t("Apply icon"), sensitive=False)
        self.apply_button.add_css_class("suggested-action")
        self.apply_button.connect("clicked", self.apply)
        actions.append(self.apply_button)
        actions.set_margin_start(24)
        actions.set_margin_end(24)
        actions.set_margin_top(12)
        actions.set_margin_bottom(16)
        outer.append(actions)
        self.name_entry = Gtk.Entry(placeholder_text=t("Application name"))
        self.name_entry.update_property([Gtk.AccessibleProperty.LABEL], [t("Application name")])
        box.insert_child_after(self.name_entry, filename)
        self.application_id = ""
        self.source_url = ""
        self.license_name = "Unknown — review required"
        self.share = Gtk.CheckButton(label=t("Share this icon when applying"))
        self.share.set_tooltip_text(
            t("Share the icon and metadata for review. No account, file paths or launch commands.")
        )
        box.insert_child_after(self.share, self.credit)
        from .community import endpoint

        try:
            endpoint()
        except ValueError:
            self.share.set_sensitive(False)
            self.share.set_tooltip_text(t("Sharing is not configured. Local icons still work."))
        add = Gtk.Button(label=t("Create launcher"))
        add.connect("clicked", self.add_launcher)
        actions.prepend(add)
        match = self.resolver.resolve(self.path)
        identity = self.resolver.resolve(self.path, read_custom=False)
        self.local_suggestions = (
            identity.candidates or [] if identity.method in {"appstream", "desktop"} else []
        )
        self.application_id = identity.application_id.removesuffix(".desktop")
        self.window_identity = (
            self.application_id if identity.method in {"desktop", "bundle"} else ""
        )
        self.name_entry.set_text(identity.name or self.path.stem)

        details = Gtk.Expander(label=t("Contribution details"))
        fields = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.id_entry = Gtk.Entry(placeholder_text=t("Application ID"), text=self.application_id)
        self.source_entry = Gtk.Entry(
            placeholder_text=t("https://example.org (optional until review)")
        )
        self.license_entry = Gtk.Entry(
            placeholder_text=t("License / attribution"), text=self.license_name
        )
        for field_title, entry in [
            (t("Application ID"), self.id_entry),
            (t("Image source"), self.source_entry),
            (t("License / attribution"), self.license_entry),
        ]:
            entry.update_property([Gtk.AccessibleProperty.LABEL], [field_title])
            fields.append(Gtk.Label(label=field_title, xalign=0))
            fields.append(entry)
        details.set_child(fields)
        box.insert_child_after(details, self.share)
        details.set_visible(False)
        self.share.connect("toggled", lambda check: details.set_visible(check.get_active()))
        contributions = Gtk.Button(label=t("My contributions"), has_frame=False)
        contributions.connect("clicked", lambda *_: Contributions(self.get_application()).present())
        box.append(contributions)

        if match.status == "resolved":
            asset = icon_path(match.icon)
            if asset:
                self.select(
                    str(asset),
                    t("Current file icon")
                    if match.method == "user-icon"
                    else t("{name} · installed application", name=match.name),
                )
            else:
                self.status.set_text(t("Original icon unavailable. Choose an image."))
        elif match.status == "ambiguous":
            self.status.set_text(t("Multiple applications found. Select an icon."))
        else:
            self.status.set_text(t("Choose an image or search the catalog."))
        self.search.set_text(application_search_name(self.path))
        GLib.idle_add(self.ensure_catalog)

    def on_close(self, *_: Any) -> bool:
        self.closed = True
        return False

    def select(self, icon: str, description: str) -> None:
        self.selected = icon
        self.preview.set_from_file(icon)
        self.preview.set_pixel_size(96)
        self.credit.set_text(description)
        self.status.set_text(t("Ready to apply"))
        self.apply_button.set_sensitive(True)

    def background(self, work: Callable[[], Any], done: Callable[[Any], None]) -> None:
        if self.busy:
            return
        self.busy = True
        self.choose_button.set_sensitive(False)
        self.apply_button.set_sensitive(False)
        self.restore.set_sensitive(False)
        self.results.set_sensitive(False)

        def finish(value: Any, error: str) -> bool:
            if self.closed:
                return False
            self.busy = False
            self.choose_button.set_sensitive(True)
            self.restore.set_sensitive(True)
            self.results.set_sensitive(True)
            self.apply_button.set_sensitive(bool(self.selected))
            if error:
                self.status.set_text(error)
            else:
                done(value)
            return False

        def worker() -> None:
            try:
                value = work()
                GLib.idle_add(finish, value, "")
            except Exception as exc:
                GLib.idle_add(finish, None, str(exc))

        Thread(target=worker, daemon=True).start()

    def ensure_catalog(self) -> bool:
        import time

        from .core import cache_dir

        catalog = cache_dir() / "catalog.json"
        if not catalog.exists() or time.time() - catalog.stat().st_mtime > CATALOG_REFRESH_SECONDS:

            def ready(_value: Any) -> None:
                if self.closed:
                    return
                self.resolver = Resolver()
                self.search_changed()

            def refresh() -> None:
                try:
                    value = sync_catalog()
                    GLib.idle_add(ready, value)
                except Exception:
                    pass

            Thread(target=refresh, daemon=True).start()
        return False

    def search_changed(self, *_: Any) -> None:
        while child := self.results.get_row_at_index(0):
            self.results.remove(child)
        for candidate in self.local_suggestions:
            asset = icon_path(candidate.get("icon", ""))
            if asset:
                button = Gtk.Button(label=candidate["name"] + t(" · installed"), has_frame=False)
                button.connect("clicked", self.pick_local, candidate, str(asset))
                self.results.append(button)
        for item in self.resolver.search(self.search.get_text()):
            button = Gtk.Button(
                label=item["name"] + "  ·  " + item["provider"],
                has_frame=False,
                halign=Gtk.Align.FILL,
            )
            button.set_tooltip_text(item["attribution"])
            button.connect("clicked", self.pick_catalog, item)
            self.results.append(button)

    def pick_local(self, _button: Any, item: dict[str, Any], asset: str) -> None:
        self.application_id = item.get("application_id", item.get("id", "")).removesuffix(
            ".desktop"
        )
        self.name_entry.set_text(item["name"])
        self.id_entry.set_text(self.application_id)
        self.source_entry.set_text("")
        self.license_entry.set_text("Unknown — review required")
        self.select(asset, t("Installed application · selected by you"))

    def pick_catalog(self, _button: Any, item: dict[str, Any]) -> None:
        if self.busy:
            return
        self.status.set_text(t("Downloading icon: {name}…", name=item["name"]))
        self.name_entry.set_text(item["name"])
        self.application_id = self.application_id or item["slug"]
        self.source_url = item.get("source", "")
        self.license_name = item.get("asset_license", "Unknown — review required")
        self.id_entry.set_text(self.application_id)
        self.source_entry.set_text(self.source_url)
        self.license_entry.set_text(self.license_name)
        self.background(
            lambda: fetch_icon(item["provider"], item["slug"], item.get("source_revision")),
            lambda path: self.select(str(path), item["attribution"]),
        )

    def choose_file(self, *_: Any) -> None:
        dialog = Gtk.FileDialog(title=t("Choose application icon"))
        dialog.set_initial_folder(Gio.File.new_for_path(str(self.path.parent)))
        filter = Gtk.FileFilter()
        filter.set_name(t("Images"))
        filter.add_pixbuf_formats()
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter)
        dialog.set_filters(filters)

        def chosen(dialog: Any, result: Any) -> None:
            try:
                file = dialog.open_finish(result)
                if file and file.get_path() and not self.closed:
                    self.source_entry.set_text("")
                    self.license_entry.set_text("Unknown — review required")
                    self.select(file.get_path(), t("Local image"))
            except GLib.Error:
                pass

        dialog.open(self, None, chosen)

    def apply(self, *_: Any) -> None:
        if self.busy or not self.selected:
            return
        try:
            apply(self.path, self.selected, replace=True)
        except Exception as exc:
            self.status.set_text(t("Could not apply icon: ") + str(exc))
            return
        refresh_notice = refresh_warning(self.path)
        applied_message = t("Icon applied.") + (" " + refresh_notice if refresh_notice else "")
        self.status.set_text(applied_message + t(" You can restore the previous icon."))
        if not self.share.get_active():
            return
        from .community import drain_outbox, enqueue, preview, submission_status

        try:
            name = self.name_entry.get_text().strip()
            app_id = self.id_entry.get_text().strip() or name.casefold().replace(" ", "-")
            payload = preview(
                app_id,
                name,
                self.selected,
                self.source_entry.get_text().strip(),
                self.license_entry.get_text().strip(),
            )
            receipt = enqueue(payload, consent=True)
        except Exception as exc:
            self.status.set_text(applied_message + t(" Sharing failed: ") + str(exc))
            return
        self.status.set_text(applied_message + t(" Contribution queued. See My contributions."))

        def submit() -> None:
            try:
                drain_outbox()
                submission_status(receipt, refresh=False)
            except Exception:
                pass

        Thread(target=submit, daemon=True).start()

    def undo(self, *_: Any) -> None:
        try:
            notice = undo(self.path)
            self.status.set_text(t("Previous icon restored.") + (" " + notice if notice else ""))
        except Exception as exc:
            self.status.set_text(str(exc))

    def add_launcher(self, *_: Any) -> None:
        from .launchers import add_launcher

        try:
            if not self.selected:
                raise ValueError(t("Select an icon first"))
            result = add_launcher(
                self.path,
                self.name_entry.get_text().strip(),
                self.selected,
                application_id=self.window_identity,
            )
            self.status.set_text(t("Launcher ready: ") + str(result.path))
        except Exception as exc:
            self.status.set_text(str(exc))


def run_contributions() -> int:
    app = Gtk.Application(
        application_id="io.github.appfaces.Contributions", flags=Gio.ApplicationFlags.NON_UNIQUE
    )
    app.connect("activate", lambda application: Contributions(application).present())
    return int(app.run([]))


class Contributions(Gtk.ApplicationWindow):  # type: ignore[misc]
    def __init__(self, app: Any) -> None:
        super().__init__(
            application=app,
            title="My contributions · App Faces",
            default_width=620,
            default_height=660,
        )
        install_style(self)
        self.closed = False
        self.busy = False
        self.connect("close-request", self.on_close)
        self.set_titlebar(Gtk.HeaderBar())
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )
        self.set_child(box)
        box.append(label(t("My contributions"), "title-1"))
        box.append(
            label(
                t("Track contributions. Edit or withdraw them while review is pending."),
                "supporting",
            )
        )
        self.status = label(t("Receipts stay on this computer."), "status-bar")
        box.append(self.status)
        self.listing = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.listing.add_css_class("boxed-list")
        empty = label(
            t("No contributions yet. Select sharing when applying an icon."),
            "supporting",
            margin_top=24,
            margin_bottom=24,
            margin_start=18,
            margin_end=18,
        )
        self.listing.set_placeholder(empty)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(self.listing)
        box.append(scroll)
        self.refresh = Gtk.Button(label=t("Refresh status"), halign=Gtk.Align.END)
        self.refresh.connect("clicked", self.refresh_all)
        box.append(self.refresh)
        self.render()

    def on_close(self, *_: Any) -> bool:
        self.closed = True
        return False

    def render(self) -> None:
        from .community import submissions

        while row := self.listing.get_row_at_index(0):
            self.listing.remove(row)
        for item in submissions():
            box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=8,
                margin_top=12,
                margin_bottom=12,
                margin_start=12,
                margin_end=12,
            )
            box.append(label(item["name"], "section-title"))
            box.append(label(status_text(item["status"]), "supporting"))
            if item["reason"]:
                box.append(label(item["reason"], "supporting"))
            actions = Gtk.Box(spacing=8)
            if not item["sent"] and item["status"] in {"pending", "failed"}:
                retry = Gtk.Button(label=t("Retry upload"))
                retry.connect("clicked", self.retry, item["id"])
                actions.append(retry)
                cancel = Gtk.Button(label=t("Cancel upload"))
                cancel.connect("clicked", self.cancel, item["id"])
                actions.append(cancel)
            elif item["sent"] and item["status"] in {"pending", "submitted", "correction"}:
                edit = Gtk.Button(label=t("Edit details"))
                edit.connect("clicked", self.edit, item)
                actions.append(edit)
                withdraw = Gtk.Button(label=t("Withdraw contribution"))
                withdraw.connect("clicked", self.confirm_withdraw, item["id"])
                actions.append(withdraw)
            box.append(actions)
            self.listing.append(box)

    def work(self, task: Callable[[], Any], message: str) -> None:
        if self.busy:
            return
        self.busy = True
        self.listing.set_sensitive(False)
        self.refresh.set_sensitive(False)
        self.status.set_text(t("Refreshing…"))

        def finish(error: str) -> bool:
            if self.closed:
                return False
            self.busy = False
            self.listing.set_sensitive(True)
            self.refresh.set_sensitive(True)
            self.render()
            self.status.set_text(
                t("Operation failed. Your data is saved. ") + error if error else message
            )
            return False

        def worker() -> None:
            try:
                task()
                GLib.idle_add(finish, "")
            except Exception as exc:
                GLib.idle_add(finish, str(exc))

        Thread(target=worker, daemon=True).start()

    def refresh_all(self, *_: Any) -> None:
        from .community import submission_status, submissions

        rows = submissions()

        def refresh() -> None:
            failures = 0
            for item in rows:
                try:
                    submission_status(item["id"])
                except OSError, ValueError:
                    failures += 1
            if failures:
                raise ValueError(
                    t("Uploads without a response: {count}. Refresh to retry.", count=failures)
                )

        self.work(refresh, t("Status updated."))

    def retry(self, _button: Any, identity: str) -> None:
        from .community import drain_outbox, retry_submission

        def send() -> None:
            retry_submission(identity)
            drain_outbox()

        self.work(send, t("Retry complete. Offline uploads remain queued."))

    def cancel(self, _button: Any, identity: str) -> None:
        from .community import cancel_submission

        self.work(lambda: cancel_submission(identity), t("Upload cancelled. Local icon unchanged."))

    def confirm_withdraw(self, _button: Any, identity: str) -> None:
        from .community import revise_submission

        dialog = Gtk.AlertDialog(
            message=t("Withdraw this contribution?"),
            detail=t("Remove it from review. Keep the local icon."),
            buttons=[t("Keep contribution"), t("Withdraw")],
            cancel_button=0,
            default_button=0,
        )

        def chosen(dialog: Any, result: Any) -> None:
            try:
                if dialog.choose_finish(result) == 1:
                    self.work(
                        lambda: revise_submission(identity),
                        t("Contribution withdrawn. Local icon unchanged."),
                    )
            except GLib.Error:
                pass

        dialog.choose(self, None, chosen)

    def edit(self, _button: Any, item: dict[str, Any]) -> None:
        from .community import revise_submission

        dialog = Gtk.Window(
            title=t("Edit contribution"), transient_for=self, modal=True, default_width=460
        )
        install_style(dialog)
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )
        dialog.set_child(box)
        box.append(label(t("Edit details"), "title-1"))
        box.append(
            label(
                t("Keep the uploaded icon. Submit metadata changes for review."),
                "supporting",
            )
        )
        entries: dict[str, Any] = {}
        for key, title in [
            ("name", t("Application name")),
            ("applicationId", t("Identifier")),
            ("sourceUrl", t("Image source")),
            ("license", t("License / attribution")),
            ("variant", t("Variant")),
        ]:
            box.append(label(title, "section-title"))
            entries[key] = Gtk.Entry(text=item[key])
            entries[key].update_property([Gtk.AccessibleProperty.LABEL], [title])
            box.append(entries[key])
        error = label("", "supporting")
        box.append(error)
        actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label=t("Cancel"))
        cancel.connect("clicked", lambda *_: dialog.close())
        actions.append(cancel)
        save = Gtk.Button(label=t("Submit correction"))
        save.add_css_class("suggested-action")
        actions.append(save)
        box.append(actions)

        def submit(*_: Any) -> None:
            metadata = {key: entry.get_text().strip() for key, entry in entries.items()}
            if not metadata["name"] or not metadata["applicationId"]:
                error.set_text(t("Enter the application name and ID."))
                return
            save.set_sensitive(False)
            cancel.set_sensitive(False)
            error.set_text(t("Submitting correction…"))

            def finish(message: str) -> bool:
                save.set_sensitive(True)
                cancel.set_sensitive(True)
                if message:
                    error.set_text(t("Could not submit. ") + message)
                else:
                    dialog.close()
                    self.render()
                    self.status.set_text(t("Correction submitted."))
                return False

            def worker() -> None:
                try:
                    revise_submission(item["id"], metadata)
                    GLib.idle_add(finish, "")
                except Exception as exc:
                    GLib.idle_add(finish, str(exc))

            Thread(target=worker, daemon=True).start()

        save.connect("clicked", submit)
        dialog.present()
