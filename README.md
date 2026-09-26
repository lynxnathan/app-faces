# App Faces

A background service for GNOME and KDE that finds icons for your applications in
online catalogs and applies them automatically.

## Features

- Downloads icons from selfh.st, Dashboard Icons and [configured forks](docs/UPSTREAMS.md).
- Uses installed launchers and embedded AppImage artwork without running the application.
- Preserves icons you chose yourself; leaves uncertain matches for manual selection.
- Searches catalogs and accepts local PNG/SVG files through an icon chooser.
- Creates application-menu launchers.
- Integrates with GNOME Files and KDE Dolphin.
- Supports [ten interface languages](docs/I18N.md), including right-to-left layouts.
- Offers [opt-in icon contributions](DEVELOPMENT.md#optional-contributions-and-backend) to a configured moderation backend.

## Install

Tested on Ubuntu 26.04 with GNOME. Requires Python 3.14+, GTK4 and a systemd user
session. Run the installer as your desktop user:

```sh
sudo apt update
sudo apt install git python3 python3-gi gir1.2-gtk-4.0 \
  gir1.2-gdkpixbuf-2.0 librsvg2-common gvfs squashfs-tools

git clone https://github.com/lynxnathan/app-faces.git
cd app-faces
/usr/bin/python3 install.py
```

Installs user-local commands, file-manager actions and a background scan that runs
about once a minute. The sharing screen is optional. Keep the checkout at its
installed path until uninstalling.

Dolphin icon previews require the [additional KDE plugin](adapters/kde/README.md).

## Use

Automatic scanning covers Downloads, Desktop, Applications and `~/.local/bin`,
plus launcher targets inside your home directory.
[Configure other folders](DEVELOPMENT.md#automatic-recognition).

To choose an icon or create a launcher, right-click an application:

- **GNOME Files:** Scripts → App Faces.
- **Dolphin:** App Faces. Press **F5** after changing an icon to refresh its preview.

Pause or resume automatic scanning:

```sh
~/.local/bin/app-faces pause
~/.local/bin/app-faces resume
```

Restore a file's previous icon and exclude it from automatic changes:

```sh
~/.local/bin/app-faces undo /path/to/application
```

## Uninstall

```sh
~/.local/bin/app-faces uninstall
```

Stops scanning, restores previous icons and removes App Faces launchers and
integrations. Keeps items you edited afterward, cached artwork and recovery records.

[Configuration](DEVELOPMENT.md#automatic-recognition) · [Development and tests](DEVELOPMENT.md#setup) ·
[Backend](backend/README.md) · [Provenance](SOURCES.md) · [Roadmap](ROADMAP.md)
