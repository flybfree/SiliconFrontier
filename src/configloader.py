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
SCENARIO_MANIFEST_FILENAME = "scenario.json"

# Default library location relative to this file's parent (project root/library/)
_DEFAULT_LIBRARY_DIR = Path(__file__).parent.parent / "library"


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_scenario_manifest(config_dir: str | Path) -> dict[str, Any]:
    """Load the scenario.json manifest for a config directory. Returns {} if absent."""
    path = Path(config_dir) / SCENARIO_MANIFEST_FILENAME
    if path.exists():
        return _load_json(path)
    return {}


def load_item_library(library_dir: str | Path | None = None) -> dict[str, Any]:
    """Load the shared item library. Returns empty library if file is absent."""
    path = Path(library_dir or _DEFAULT_LIBRARY_DIR) / "items.json"
    if path.exists():
        return _load_json(path)
    return {"items": {}}


def load_relationship_presets(library_dir: str | Path | None = None) -> dict[str, Any]:
    """Load the shared relationship preset library. Returns empty presets if absent."""
    path = Path(library_dir or _DEFAULT_LIBRARY_DIR) / "relationship_presets.json"
    if path.exists():
        return _load_json(path)
    return {"presets": {}}


def resolve_item_placements(world_data: dict[str, Any], item_library: dict[str, Any]) -> None:
    """
    Expand item_placements references into world_data["items"] using the library.

    item_placements entries: {"item_id": "plasma_wrench", "location": "engineering"}
    Inline items in world_data["items"] are preserved and take precedence.
    """
    placements = world_data.get("item_placements", [])
    if not placements:
        return
    library_items = item_library.get("items", {})
    items = world_data.setdefault("items", {})
    for placement in placements:
        item_id = placement.get("item_id")
        location = placement.get("location")
        if not item_id or item_id in items:
            continue
        if item_id not in library_items:
            continue
        item_def = copy.deepcopy(library_items[item_id])
        item_def["location"] = location
        item_def.setdefault("owner", None)
        # Allow per-placement field overrides (e.g. custom knowledge)
        for key, value in placement.items():
            if key not in ("item_id", "location"):
                item_def[key] = value
        items[item_id] = item_def


def resolve_relationship_presets(
    slots_data: dict[str, Any],
    world_data: dict[str, Any],
    presets: dict[str, Any]
) -> None:
    """
    Expand relationship preset references from slots_data into world_data relationships.

    relationships entries: {"from": "agent_a", "to": "agent_b", "preset": "rivals"}
    Relationships already present in world_data are not overwritten.
    """
    relationships_list = slots_data.get("relationships", [])
    if not relationships_list:
        return
    preset_map = presets.get("presets", {})
    rels = world_data.setdefault("relationships", {})
    suspicions = world_data.setdefault("suspicions", {})
    for entry in relationships_list:
        from_id = entry.get("from")
        to_id = entry.get("to")
        preset_name = entry.get("preset", "neutral")
        if not from_id or not to_id:
            continue
        preset = preset_map.get(preset_name, {"trust": 50, "affinity": 50, "suspicion": 0})
        # Don't overwrite manually specified relationships
        if to_id not in rels.get(from_id, {}):
            rels.setdefault(from_id, {})[to_id] = {
                "trust": preset["trust"],
                "affinity": preset["affinity"],
                "notes": f"[{preset_name}]"
            }
        if to_id not in suspicions.get(from_id, {}):
            suspicions.setdefault(from_id, {})[to_id] = preset.get("suspicion", 0)


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
