"""Verify hand, visible, and concealed inventory slots remain distinct."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from actionparser import ActionParser
from worldstate import WorldState


class Agent:
    agent_id = "alpha"


def main() -> None:
    world = WorldState({
        "locations": {"bay": {"name": "Bay", "connected_to": []}},
        "agents": {"alpha": {"location": "bay", "name": "Alpha", "inventory": []}, "bravo": {"location": "bay", "name": "Bravo", "inventory": []}},
        "items": {
            "tool": {"name": "Tool", "location": "bay", "owner": None, "portable": True},
            "supply": {"name": "Supply", "location": "bay", "owner": None, "portable": True},
            "clue": {"name": "Clue", "location": "bay", "owner": None, "portable": True, "hidden": True},
        },
    })
    parser = ActionParser(world)
    agent = Agent()
    assert parser.execute(agent, {"action": "PICKUP", "action_target": "Tool"})[0]
    assert parser.execute(agent, {"action": "PICKUP", "action_target": "Supply"})[0]
    assert parser.execute(agent, {"action": "PICKUP", "action_target": "Clue"})[0]
    slots = {item["name"]: world.inventory_slot(item) for item in world.find_items_by_owner("alpha")}
    assert slots == {"Tool": "hand", "Supply": "visible", "Clue": "concealed"}
    snapshot = world.get_snapshot_for_agent("bravo")
    seen = snapshot["visible_agent_inventory"]["alpha"]
    assert {entry["name"] for entry in seen} == {"Tool", "Supply"}
    assert all(entry["name"] != "Clue" for entry in seen)
    assert parser.execute(agent, {"action": "STOW", "action_target": "Tool"})[0] is False
    assert parser.execute(agent, {"action": "READY", "action_target": "Supply"})[0] is False
    print("[PASS] Three inventory slots preserve public and concealed visibility")


if __name__ == "__main__":
    main()
