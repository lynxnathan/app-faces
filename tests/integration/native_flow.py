import argparse
import json

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib


def children(root):
    for index in range(root.get_child_count()):
        item = root.get_child_at_index(index)
        if item:
            yield item


def walk(root, depth=0):
    if depth > 45:
        return
    yield root
    for item in children(root):
        yield from walk(item, depth + 1)


def find_window(title):
    for app in children(Atspi.get_desktop(0)):
        for window in children(app):
            if window.get_name() == title:
                return window
    raise RuntimeError("Target window not found: " + title)


parser = argparse.ArgumentParser()
parser.add_argument("operation", choices=["inspect", "select", "action", "text", "tree", "click"])
parser.add_argument("--window", required=True)
parser.add_argument("--name", default="")
parser.add_argument("--role", default="")
parser.add_argument("--action", default="click")
parser.add_argument("--value", default="")
args = parser.parse_args()
if args.operation == "click":
    parser.error(
        "Synthetic pointer input is disabled. Use tests/integration/native-e2e.sh for isolated native UI tests."
    )
window = find_window(args.window)
nodes = [
    n
    for n in walk(window)
    if (not args.name or n.get_name() == args.name)
    and (not args.role or n.get_role_name() == args.role)
]
if args.operation == "tree":
    for n in nodes:
        if n.get_name():
            print(json.dumps({"name": n.get_name(), "role": n.get_role_name()}, ensure_ascii=False))
    raise SystemExit()
assert len(nodes) == 1, f"Expected one bound node, found {len(nodes)}"
node = nodes[0]
if args.operation == "inspect":
    c = node.get_component_iface()
    if c:
        e = c.get_extents(Atspi.CoordType.SCREEN)
        print("screen_extents", e.x, e.y, e.width, e.height)
    for i in range(6):
        print(
            node.get_role_name(),
            node.get_name(),
            list(node.get_interfaces()),
            node.get_index_in_parent(),
        )
        node = node.get_parent()
elif args.operation == "select":
    parent = node.get_parent()
    selection = parent.get_selection_iface()
    assert selection and selection.select_child(node.get_index_in_parent())
    assert node.get_state_set().contains(Atspi.StateType.SELECTED)
    print("Bound item selected")
elif args.operation == "action":
    action = node.get_action_iface()
    names = [action.get_action_name(i) for i in range(action.get_n_actions())]
    assert args.action in names, names
    assert action.do_action(names.index(args.action))
    loop = GLib.MainLoop()
    GLib.timeout_add(600, lambda: (loop.quit(), False)[1])
    loop.run()
    print("Bound action completed: " + args.action)
elif args.operation == "text":
    assert node.get_editable_text_iface().set_text_contents(args.value)
    print("Bound text entered")
