import argparse
import json
from pathlib import Path

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402 — select GI version first

parser = argparse.ArgumentParser()
parser.add_argument("operation", choices=["apps", "tree", "action", "text"])
parser.add_argument("--app", type=int)
parser.add_argument("--path", default="")
parser.add_argument("--value", default="")
parser.add_argument("--secret-file", type=Path)
parser.add_argument("--action", type=int, default=0)
parser.add_argument("--filter", default="")
args = parser.parse_args()
desktop = Atspi.get_desktop(0)
if args.operation == "apps":
    print(
        [
            (
                i,
                desktop.get_child_at_index(i).get_name(),
                desktop.get_child_at_index(i).get_child_count(),
            )
            for i in range(desktop.get_child_count())
        ]
    )
    raise SystemExit()
node = desktop.get_child_at_index(args.app)
for index in args.path.split("/"):
    if index:
        node = node.get_child_at_index(int(index))
if args.operation == "text":
    value = args.secret_file.read_text().strip() if args.secret_file else args.value
    assert node.get_editable_text_iface().set_text_contents(value)
    print("Bound field updated" + (" from private file; value omitted" if args.secret_file else ""))
elif args.operation == "action":
    action = node.get_action_iface()
    assert action.do_action(args.action)
    print("Bound action dispatched")
else:
    count = [0]

    def walk(item, path, depth):
        if depth > 40 or count[0] > 1400:
            return
        count[0] += 1
        try:
            role = item.get_role_name()
            name = item.get_name()
            actions = item.get_action_iface()
            labels = (
                [actions.get_action_name(i) for i in range(actions.get_n_actions())]
                if actions
                else []
            )
            states = item.get_state_set()
            state = [
                k
                for k in ["SHOWING", "SELECTED", "CHECKED", "EXPANDED"]
                if states.contains(getattr(Atspi.StateType, k))
            ]
            if name and (not args.filter or args.filter.casefold() in name.casefold()):
                print(
                    json.dumps(
                        dict(path=path, role=role, name=name, actions=labels, state=state),
                        ensure_ascii=False,
                    )
                )
            for index in range(item.get_child_count()):
                walk(item.get_child_at_index(index), path + "/" + str(index), depth + 1)
        except Exception as error:
            print(json.dumps(dict(path=path, error=type(error).__name__)))

    walk(node, args.path, 0)
