"""Regression checks for durable, target-aware default-scenario tool use."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from tool_registry import validate_tool_use
from worldstate import WorldState


def main() -> None:
    root = Path(__file__).parent
    world_data = json.loads((root / "scenarios" / "default" / "world_state.json").read_text(encoding="utf-8"))

    placements = {entry["item_id"]: entry for entry in world_data["item_placements"]}
    wrench = placements["plasma_wrench"]
    scanner = placements["oxygen_scanner"]
    module = world_data["items"]["data_module"]
    assert wrench["tool"]["capabilities"] == ["inspect_reactor_control"]
    assert scanner["tool"]["capabilities"] == ["inspect_oxygen_generator"]
    assert "reactor_baseline_recorded" in wrench["use_effect"]["add_location_effects"]
    assert "oxygen_baseline_recorded" in scanner["use_effect"]["add_location_effects"]
    assert "forensic_audit_indexed" in module["use_effect"]["add_location_effects"]

    world = WorldState({
        "locations": {
            "command_deck": {"facilities": ["secure_terminal"], "systems": {}},
        },
        "agents": {"analyst": {"location": "command_deck", "inventory": []}},
        "items": {},
    })
    allowed, feedback = validate_tool_use(world, "analyst", module, "secure_terminal")
    assert allowed, feedback
    denied, _ = validate_tool_use(world, "analyst", module, "reactor_control")
    assert not denied
    print("[PASS] Default tools have durable effects and only accept configured targets")


if __name__ == "__main__":
    main()
