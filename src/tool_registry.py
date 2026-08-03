"""Deterministic registry for target-aware fabricated-tool capabilities."""

from __future__ import annotations

import re
from typing import Any


CAPABILITIES: dict[str, dict[str, str | None]] = {
    "inspect_reactor_control": {"target": "reactor_control", "location": None},
    "inspect_oxygen_generator": {"target": "oxygen_generator", "location": "hydroponics_bay"},
    "restore_reactor_control": {"target": "reactor_control", "location": None},
    "alter_life_support_status": {"target": "life_support_console", "location": "command_deck"},
    "broadcast_coordination_alert": {"target": None, "location": None},
    "stabilize_self": {"target": None, "location": None},
}


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _matches(target: str, expected: str) -> bool:
    return _normalize(target) == _normalize(expected)


def validate_tool_use(world: Any, agent_id: str, item: dict[str, Any], target: str) -> tuple[bool, str]:
    """Validate a fabricated tool's declared capability and optional target.

    Capability labels are not executable code. This registry limits them to
    known simulation operations and ensures any target agrees with the recipe's
    declared effect before orchestration applies it.
    """
    tool = item.get("tool")
    if not tool:
        if target:
            return False, f"Failure: {item.get('name', 'This item')} has no target-aware capability."
        return True, ""

    capabilities = tool.get("capabilities", [])
    if not isinstance(capabilities, list) or not capabilities:
        return False, f"Failure: {item.get('name', 'This tool')} has no declared capability."

    for capability in capabilities:
        spec = CAPABILITIES.get(str(capability))
        if not spec:
            return False, f"Failure: Unknown simulation capability '{capability}'."
        expected_target = spec["target"]
        if expected_target is None:
            if target:
                return False, f"Failure: {item.get('name', 'This tool')} does not take a target."
            continue
        if not target:
            return False, f"Failure: {item.get('name', 'This tool')} requires target '{expected_target}'."
        if not _matches(target, str(expected_target)):
            return False, f"Failure: {item.get('name', 'This tool')} cannot target '{target}'. Valid target: {expected_target}."
        location = spec["location"] or world.get_agent_location(agent_id)
        if expected_target not in world.get_location_systems(str(location)):
            return False, f"Failure: Target system '{expected_target}' is unavailable."
    return True, ""
