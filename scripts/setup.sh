#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# GTK/GIO bindings are maintained by the desktop distribution, not vendored.
/usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "4.0"); from gi.repository import Gtk, Gio'
if [ ! -f .venv/pyvenv.cfg ]; then
    uv venv --python /usr/bin/python3 --system-site-packages
fi
.venv/bin/python -c 'import gi'
uv sync --frozen
