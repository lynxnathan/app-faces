from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

app = Gtk.Application(
    application_id="io.github.appfaces.Selection", flags=Gio.ApplicationFlags.NON_UNIQUE
)


def activate(app: Any) -> None:
    window = Gtk.ApplicationWindow(application=app, title="App Faces", default_width=380)
    box = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=16,
        margin_start=24,
        margin_end=24,
        margin_top=24,
        margin_bottom=24,
    )
    box.append(
        Gtk.Label(label="Select one application file, then choose\nScripts → App Faces.", wrap=True)
    )
    button = Gtk.Button(label="Got it")
    button.connect("clicked", lambda *_: window.close())
    box.append(button)
    window.set_child(box)
    window.present()


app.connect("activate", activate)
app.run([])
