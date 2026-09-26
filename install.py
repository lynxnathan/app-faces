#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

from app_faces.installation import install, install_kde_plugin, uninstall

parser = argparse.ArgumentParser(description="Install App Faces, or restore icons and uninstall")
parser.add_argument("--uninstall", action="store_true")
parser.add_argument("--no-service-start", action="store_true")
parser.add_argument(
    "--keep-icons", action="store_true", help="On uninstall, explicitly retain applied icons"
)
parser.add_argument(
    "--no-onboarding", action="store_true", help="Skip opening the optional contribution invitation"
)
parser.add_argument("--kde-plugin", type=Path, help="Compiled optional KDE thumbnail plugin")
parser.add_argument("--qt-plugin-dir", type=Path, help="User-local Qt6 plugin search root")
args = parser.parse_args()
if bool(args.kde_plugin) != bool(args.qt_plugin_dir):
    parser.error("--kde-plugin and --qt-plugin-dir must be supplied together")
if args.uninstall and args.kde_plugin:
    parser.error("Do not combine plugin installation and uninstall")
if os.getuid() == 0:
    raise SystemExit("Run as your desktop user, not root.")
root = Path(__file__).resolve().parent
result = (
    uninstall(not args.no_service_start, not args.keep_icons)
    if args.uninstall
    else install(root, not args.no_service_start)
)
if args.kde_plugin:
    result["kde"] = install_kde_plugin(args.kde_plugin, args.qt_plugin_dir)
print(json.dumps(result, indent=2))
if not args.uninstall and not args.no_onboarding and not args.no_service_start:
    from app_faces.core import data_dir
    from app_faces.onboarding import run

    if not (data_dir() / "onboarding-seen").exists():
        run()
