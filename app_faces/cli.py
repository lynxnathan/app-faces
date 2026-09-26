import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import Resolver, fetch_icon, sync_catalog
from .state import apply, undo


def main() -> int:
    parser = argparse.ArgumentParser(description="Application artwork, desktop entries first")
    commands = parser.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser("resolve", help="Read-only identity and icon lookup")
    resolve.add_argument("path", type=Path)
    resolve.add_argument(
        "--sha256", action="store_true", help="Opt in to potentially expensive hashing"
    )
    commands.add_parser("automatic", help="Background application scan")
    commands.add_parser("sync", help="Download public catalog metadata; uploads nothing")
    commands.add_parser(
        "sources", help="Validate and list upstreams from ~/.config/app-faces/upstreams.toml"
    )
    search = commands.add_parser("search", help="Search downloaded metadata offline")
    search.add_argument("query")
    gui = commands.add_parser("gui", help="Open the icon chooser for a file")
    gui.add_argument("path", type=Path)
    change = commands.add_parser("apply", help="Apply resolved desktop icon or an explicit icon")
    change.add_argument("path", type=Path)
    change.add_argument("--icon")
    change.add_argument(
        "--provider", help="Configured source ID, or community; see app-faces sources"
    )
    change.add_argument("--slug")
    change.add_argument("--replace", action="store_true")
    reset = commands.add_parser("undo", help="Restore the icon preceding our change")
    reset.add_argument("path", type=Path)
    commands.add_parser(
        "rollback", help="Restore managed icons and remove unedited generated launchers"
    )
    uninstall_parser = commands.add_parser(
        "uninstall", help="Stop service, restore icons and remove integrations"
    )
    uninstall_parser.add_argument("--keep-icons", action="store_true")
    commands.add_parser("pause", help="Pause automatic icon application")
    commands.add_parser("resume", help="Resume automatic icon application")
    commands.add_parser("onboard", help="Optional anonymous contribution invitation")
    catalog = commands.add_parser("catalog", help="Import or roll back local recognition metadata")
    catalog_choice = catalog.add_mutually_exclusive_group(required=True)
    catalog_choice.add_argument("--import-file", type=Path)
    catalog_choice.add_argument("--revision")
    launch = commands.add_parser("add-launcher", help="Explicitly add an application launcher")
    launch.add_argument("path", type=Path)
    launch.add_argument("--name", required=True)
    launch.add_argument("--icon", required=True)
    launch.add_argument("--app-id", default="")
    launch.add_argument("--wm-class", default="")
    remove = commands.add_parser("remove-launcher", help="Remove an unedited generated launcher")
    remove.add_argument("path", type=Path)
    commands.add_parser("contributions", help="Manage your anonymous contributions")
    commands.add_parser("outbox", help="Inspect anonymous submission queue status")
    submission = commands.add_parser(
        "submission", help="Check, cancel or retry an anonymous contribution"
    )
    submission.add_argument("identity")
    submission.add_argument(
        "--action", choices=["status", "cancel", "retry", "withdraw"], default="status"
    )
    submit = commands.add_parser("submit", help="Explicitly share artwork with consent")
    submit.add_argument("--app-id", required=True)
    submit.add_argument("--name", required=True)
    submit.add_argument("--icon", required=True)
    submit.add_argument("--source", default="")
    submit.add_argument("--license", default="Unknown — review required")
    submit.add_argument("--consent", action="store_true")
    args = parser.parse_args()
    result: Any
    try:
        if args.command == "gui":
            from .ui import run

            return run(args.path)
        if args.command == "contributions":
            from .ui import run_contributions

            return run_contributions()
        if args.command == "onboard":
            from .onboarding import run as run_onboarding

            return run_onboarding()
        if args.command == "uninstall":
            from .installation import uninstall

            result = uninstall(restore=not args.keep_icons)
        elif args.command in {"pause", "resume"}:
            from .automatic import set_enabled

            set_enabled(args.command == "resume")
            result = dict(automatic_enabled=args.command == "resume")
        elif args.command == "rollback":
            from .automatic import set_enabled
            from .launchers import rollback_launchers
            from .state import rollback_all

            set_enabled(False)
            from .installation import systemctl

            systemctl("stop", "app-faces.service", missing_ok=True)
            result = dict(
                automatic_enabled=False, icons=rollback_all(), launchers=rollback_launchers()
            )
        elif args.command == "add-launcher":
            from .launchers import add_launcher

            launcher = add_launcher(args.path, args.name, args.icon, args.app_id, args.wm_class)
            result = dict(path=str(launcher.path), reused=launcher.reused)
        elif args.command == "remove-launcher":
            from .launchers import remove_launcher

            remove_launcher(args.path)
            result = dict(removed=str(args.path))
        elif args.command == "catalog":
            from .catalog import import_catalog, rollback

            if args.import_file:
                result = dict(revision=import_catalog(args.import_file))
            elif args.revision:
                result = rollback(args.revision)
            else:
                raise ValueError("Choose --import-file or --revision")
        elif args.command == "outbox":
            from .core import data_dir

            result = []
            for file in (data_dir() / "outbox").glob("*.json"):
                item = json.loads(file.read_text())
                result.append(dict(id=file.stem, status=item["status"], attempts=item["attempts"]))
        elif args.command == "submission":
            from .community import (
                cancel_submission,
                retry_submission,
                revise_submission,
                submission_status,
            )

            if args.action == "withdraw":
                revise_submission(args.identity)
            elif args.action == "cancel":
                cancel_submission(args.identity)
            elif args.action == "retry":
                retry_submission(args.identity)
            result = submission_status(args.identity)
        elif args.command == "submit":
            from .community import drain_outbox, enqueue, preview

            if not args.consent:
                raise ValueError(
                    "Use --consent only after reviewing the application identity and icon"
                )
            payload = preview(args.app_id, args.name, args.icon, args.source, args.license)
            receipt = enqueue(payload, consent=True)
            result = dict(receipt=receipt, delivery=drain_outbox())
        elif args.command == "automatic":
            from .automatic import run_once

            result = run_once()
        elif args.command == "sources":
            from dataclasses import asdict

            from .upstreams import sources

            result = [asdict(source) for source in sources().values()]
        elif args.command == "sync":
            result = sync_catalog()
        elif args.command == "search":
            result = Resolver().search(args.query)
        elif args.command == "resolve":
            result = Resolver().resolve(args.path, fingerprint=args.sha256).to_dict()
        elif args.command == "undo":
            undo(args.path)
            result = {"restored": str(args.path)}
        else:
            icon = args.icon
            if args.provider:
                if not args.slug:
                    raise ValueError("--provider requires --slug")
                icon = str(fetch_icon(args.provider, args.slug))
            if not icon:
                match = Resolver().resolve(args.path)
                if match.status != "resolved" or match.method not in {
                    "desktop",
                    "bundle",
                    "sha256",
                }:
                    raise ValueError("No unique desktop icon; select artwork in the chooser")
                icon = match.icon
            result = {"applied": apply(args.path, icon, args.replace)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"app-faces: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
