"""Regression coverage for private map discovery and known-route perception."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from worldstate import WorldState


world = WorldState({
    "locations": {
        "start": {"name": "Start", "description": "", "connected_to": ["junction"], "systems": {}},
        "junction": {"name": "Junction", "description": "", "connected_to": ["start", "target"], "systems": {}},
        "target": {
            "name": "Target Room", "description": "", "connected_to": ["junction"],
            "systems": {"target_system": {"name": "Target System", "status": "ONLINE"}},
        },
    },
    "items": {}, "agents": {}, "relationships": {}, "suspicions": {},
})

world.register_agent("explorer", "start")
initial = world.get_snapshot_for_agent("explorer")
assert set(initial["locations"]) == {"start", "junction"}
assert initial["known_systems"] == []

assert world.set_agent_location("explorer", "junction")
middle = world.get_snapshot_for_agent("explorer")
assert set(middle["locations"]) == {"start", "junction", "target"}
assert middle["known_systems"] == []

assert world.set_agent_location("explorer", "target")
discovered = world.get_snapshot_for_agent("explorer")
target = next(entry for entry in discovered["known_systems"] if entry["system_id"] == "target_system")
assert target["route"] == ["target"]
assert discovered["known_map"]["target"]["explored"] is True

world.set_agent_location("explorer", "start")
routed = world.get_snapshot_for_agent("explorer")
target = next(entry for entry in routed["known_systems"] if entry["system_id"] == "target_system")
assert target["route"] == ["start", "junction", "target"]

print("[PASS] Agents discover map routes and system targets through exploration")
