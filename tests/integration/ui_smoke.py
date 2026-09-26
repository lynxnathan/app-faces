import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
from gi.repository import Gio, GLib, Graphene, Gtk

from app_faces.ui import Chooser

app = Gtk.Application(
    application_id="io.github.appfaces.Smoke", flags=Gio.ApplicationFlags.NON_UNIQUE
)
result = {"ok": False}


def activate(app):
    w = Chooser(app, Path("/usr/bin/nautilus"))
    w.present()

    def capture():
        try:
            assert w.get_width() >= 500
            assert w.selected, "Desktop icon did not resolve"
            snapshot = Gtk.Snapshot()
            paintable = Gtk.WidgetPaintable.new(w)
            paintable.snapshot(snapshot, float(w.get_width()), float(w.get_height()))
            node = snapshot.to_node()
            texture = w.get_renderer().render_texture(
                node, Graphene.Rect().init(0, 0, w.get_width(), w.get_height())
            )
            texture.save_to_png(str(Path(__file__).resolve().parents[2] / "state/chooser.png"))
            print("GTK window layout and desktop-icon preview: PASS")
            result["ok"] = True
        except Exception as exc:
            print(type(exc).__name__, str(exc), file=sys.stderr)
        finally:
            w.close()
            app.quit()
        return False

    GLib.timeout_add(1500, capture)


app.connect("activate", activate)
app.run([])
raise SystemExit(0 if result["ok"] else 1)
