import json
import sys
from pathlib import Path

from icon_render_match import match_icon

output = Path(sys.argv[1])
result_file = output / "result.json"
result = json.loads(result_file.read_text())
assert result["passed"], result
bounds = tuple(int(value) for value in result["dockPosition"] + result["dockSize"])
match = match_icon(output / "dock.png", Path(sys.argv[2]), bounds)
result.update(renderedArtwork=match, passed=bool(match["matched"]))
result_file.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
assert match["matched"], "Dock pixels do not match the expected artwork"
