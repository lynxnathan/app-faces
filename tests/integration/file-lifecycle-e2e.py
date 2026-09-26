#!/usr/bin/python3

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from gi.repository import Gio

from app_faces.automatic import run_once
from app_faces.catalog import publish
from app_faces.core import atomic_json, custom_icon, data_dir
from app_faces.state import rollback_all, set_metadata, undo


def main():
    assert os.getuid() != 0
    project = Path(__file__).resolve().parents[2]
    result = {"passed": False, "checks": {}, "executablesRun": False, "backend": "real GVFS"}
    checks = result["checks"]
    try:
        with tempfile.TemporaryDirectory(prefix="app-faces-file-lifecycle-") as directory:
            root = Path(directory)
            for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
                os.environ[key] = str(root / key.lower())
            apps = root / "apps"
            apps.mkdir()
            atomic_json(
                root / "xdg_config_home/app-faces/config.json",
                {"directories": [str(apps)], "automatic_enabled": True},
            )

            (root / "xdg_config_home/app-faces/upstreams.toml").write_text(
                '[[sources]]\nid="selfhst"\nenabled=false\n'
                '[[sources]]\nid="dashboard"\nenabled=false\n'
            )
            icon = project / "state/native-e2e/upstream-applied-icon.png"
            assert icon.is_file()
            original = apps / "known-app"
            shutil.copyfile("/usr/bin/true", original)
            original.chmod(0o700)
            os.utime(original, (1, 1))
            publish(
                {
                    "version": 1,
                    "icons": [],
                    "fingerprints": {
                        hashlib.sha256(original.read_bytes()).hexdigest(): {
                            "id": "org.appfaces.LifecycleFixture",
                            "name": "Lifecycle fixture",
                            "icon": str(icon),
                            "source": "Explicit test-only mapping; never executed",
                        }
                    },
                }
            )

            def scan():
                value = run_once()
                assert not value["errors"], value
                return value

            first = scan()
            assert len(first["applied"]) == 1 and custom_icon(original)
            applied = custom_icon(original)
            before = original.stat()
            moved = apps / "renamed-app"
            Gio.File.new_for_path(str(original)).move(
                Gio.File.new_for_path(str(moved)), Gio.FileCopyFlags.NONE, None, None
            )
            assert moved.stat().st_ino == before.st_ino
            assert custom_icon(moved) == applied, "Files-style move must preserve GVFS icon"
            scan()
            journal = json.loads((data_dir() / "changes.json").read_text())
            assert str(moved) in journal and str(original) not in journal
            undo(moved)
            assert not custom_icon(moved)
            assert not scan()["applied"]
            checks["moveRetainsIconAndMigratesJournal"] = True
            checks["undoAtNewPathRestoresAndSuppressesReapply"] = True

            replace_target = apps / "replace-app"
            shutil.copyfile("/usr/bin/true", replace_target)
            replace_target.chmod(0o700)
            os.utime(replace_target, (1, 1))
            assert scan()["applied"]
            stale = custom_icon(replace_target)
            replacement = root / "replacement"
            shutil.copyfile("/usr/bin/false", replacement)
            replacement.chmod(0o700)
            os.utime(replacement, (1, 1))
            replacement.replace(replace_target)

            assert custom_icon(replace_target) == stale
            try:
                undo(replace_target)
            except ValueError as error:
                assert "replaced" in str(error)
            else:
                raise AssertionError("Undo must not mutate a replacement inode")
            assert not scan()["applied"]
            assert not custom_icon(replace_target), (
                "Unknown replacement must lose stale automatic art"
            )
            checks["replacementRefusesOldUndoAndClearsStaleAutomaticIcon"] = True

            external = apps / "external-choice"
            shutil.copyfile("/usr/bin/true", external)
            external.chmod(0o700)
            os.utime(external, (1, 1))
            assert scan()["applied"]
            user_choice = "application-x-executable"
            set_metadata(external, user_choice)
            assert not scan()["applied"] and custom_icon(external) == user_choice
            recovery = rollback_all()
            assert custom_icon(external) == user_choice and recovery["preserved"]
            checks["externalChoiceSurvivesScanAndGlobalRollback"] = True
            set_metadata(external, "")
            result["passed"] = True
    except Exception as error:
        result["error"] = str(error)
        raise
    finally:
        (project / "state/file-lifecycle-e2e.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
