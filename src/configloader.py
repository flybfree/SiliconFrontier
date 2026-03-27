"""
Configuration helpers for reusable agent definitions and active simulation slots.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


AGENT_DEFINITIONS_FILENAME = "agent_definitions.json"
SIMULATION_AGENTS_FILENAME = "simulation_agents.json"
LEGACY_AGENTS_FILENAME = "agents_config.json"


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_agent_configuration(config_dir: str | Path = "data") -> tuple[dict[str, Any], dict[str, Any]]:
    """Load agent definitions plus active simulation slots, with legacy fallback."""
    config_path = Path(config_dir)
    definitions_path = config_path / AGENT_DEFINITIONS_FILENAME
    slots_path = config_path / SIMULATION_AGENTS_FILENAME

    if definitions_path.exists() and slots_path.exists():
        return _load_json(definitions_path), _load_json(slots_path)

    legacy_path = config_path / LEGACY_AGENTS_FILENAME
    legacy = _load_json(legacy_path)
    definitions = {"agents": []}
    slots = {"slots": []}

    for agent_cfg in legacy.get("agents", []):
        definition = {
            "definition_id": agent_cfg["agent_id"],
            "name": agent_cfg["name"],
            "role": agent_cfg.get("role", "crew member"),
            "archetype": agent_cfg.get("archetype", "standard"),
            "perception": agent_cfg.get("perception", 50),
            "persona": agent_cfg["persona"],
            "secret_goal": agent_cfg["secret_goal"]
        }
        slot = {
            "slot_id": agent_cfg["agent_id"],
            "instance_id": agent_cfg["agent_id"],
            "definition_id": agent_cfg["agent_id"],
            "starting_location": agent_cfg["starting_location"],
            "inventory": list(agent_cfg.get("inventory", []))
        }
        definitions["agents"].append(definition)
        slots["slots"].append(slot)

    return definitions, slots


def save_agent_definitions(definitions: dict[str, Any], config_dir: str | Path = "data") -> None:
    """Persist reusable agent definitions."""
    _save_json(Path(config_dir) / AGENT_DEFINITIONS_FILENAME, definitions)


def save_simulation_slots(slots: dict[str, Any], config_dir: str | Path = "data") -> None:
    """Persist active simulation slots."""
    _save_json(Path(config_dir) / SIMULATION_AGENTS_FILENAME, slots)


def save_world_state(world_state: dict[str, Any], config_dir: str | Path = "data") -> None:
    """Persist world_state.json for a scenario/config directory."""
    _save_json(Path(config_dir) / "world_state.json", world_state)


def build_agent_instances(
    definitions: dict[str, Any],
    slots: dict[str, Any]
) -> list[dict[str, Any]]:
    """Materialize active slot configs by merging reusable definitions with slot state."""
    definition_map = {
        agent_def["definition_id"]: agent_def
        for agent_def in definitions.get("agents", [])
    }
    materialized = []

    for slot in slots.get("slots", []):
        definition = definition_map.get(slot.get("definition_id"))
        if not definition:
            continue

        agent_cfg = copy.deepcopy(definition)
        agent_cfg["slot_id"] = slot["slot_id"]
        agent_cfg["instance_id"] = slot.get("instance_id", slot["slot_id"])
        agent_cfg["agent_id"] = agent_cfg["instance_id"]
        agent_cfg["starting_location"] = slot["starting_location"]
        agent_cfg["inventory"] = list(slot.get("inventory", []))
        materialized.append(agent_cfg)

    return materialized
