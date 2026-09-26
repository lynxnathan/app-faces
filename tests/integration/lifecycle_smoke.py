import json
import os
import tempfile
from pathlib import Path

from app_faces.core import custom_icon
from app_faces.installation import install, uninstall
from app_faces.launchers import add_launcher
from app_faces.state import apply

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="app-faces-lifecycle-") as temporary:
    home = Path(temporary)
    os.environ.update(
        HOME=str(home), XDG_DATA_HOME=str(home / "data"), XDG_CONFIG_HOME=str(home / "config")
    )
    first = install(root, activate=False)
    target = home / "sample-app"
    target.write_text("#!/bin/sh\nexit 0\n")
    target.chmod(0o755)
    icon = home / "icon.svg"
    icon.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="blue"/></svg>'
    )
    applied = apply(target, str(icon))
    assert custom_icon(target) == applied
    launcher = add_launcher(target, "Lifecycle fixture", applied)
    assert launcher.path.exists()
    report = uninstall(activate=False)
    assert custom_icon(target) == ""
    assert not launcher.path.exists()
    assert all(not Path(path).exists() for path in first["installed"])
    assert report["icons"]["restored"] == [str(target)]
    assert report["launchers"]["removed"] == [str(launcher.path)]
    assert not uninstall(activate=False)["removed"]
    install(root, activate=False)
    assert uninstall(activate=False)["removed"]
    result = dict(
        real_gvfs_restore=True,
        launcher_removed=True,
        integrations_removed=True,
        uninstall_idempotent=True,
        reinstall_supported=True,
    )
(root / "state/lifecycle-integration.json").write_text(json.dumps(result, indent=2) + "\n")
print("Real GVFS + isolated install/uninstall/reinstall: 5 checks passed")
