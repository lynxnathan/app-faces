import argparse

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

parser = argparse.ArgumentParser()
parser.add_argument("--app-id", required=True)
args = parser.parse_args()
app = Gtk.Application(application_id=args.app_id, flags=Gio.ApplicationFlags.NON_UNIQUE)


def activate(application):
    window = Gtk.ApplicationWindow(
        application=application,
        title="App Faces dock fixture",
        default_width=320,
        default_height=200,
    )
    window.set_child(Gtk.Label(label="Application identity fixture"))
    window.present()


app.connect("activate", activate)
raise SystemExit(app.run([]))
