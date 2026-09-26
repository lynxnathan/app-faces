import tempfile
from pathlib import Path

from app_faces.core import custom_icon
from app_faces.state import apply, undo

with tempfile.TemporaryDirectory(prefix="app-faces-integration-") as d:
    target = Path(d) / "example"
    target.write_text("never executed")
    icon = Path(d) / "icon.svg"
    icon.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"/>')
    applied = apply(target, str(icon))
    assert custom_icon(target) == applied
    undo(target)
    assert custom_icon(target) == ""
    print("Real GVFS apply/undo: PASS")
