"""
WorldState - The Physics Engine of Silicon Frontier

Provides the "Ground Truth" for all simulation state. Prevents agents from
hallucinating objects by maintaining strict validation of locations, items,
and their relationships.
"""

import json
from pathlib import Path
from typing import Any


class WorldState:
    """
    The central truth table for the simulation environment.

    This class enforces deterministic boundaries - if something isn't in
    the WorldState dictionary, it doesn't exist regardless of what the LLM claims.
    """

    def __init__(self, data: dict | None = None):
        """Initialize world state from dict or empty."""
        self._data = data or {
            "locations": {},
            "items": {},
            "agents": {},
            "relationships": {},
            "suspicions": {}
        }
        self._data.setdefault("locations", {})
        self._data.setdefault("items", {})
        self._data.setdefault("agents", {})
        self._data.setdefault("relationships", {})
        self._data.setdefault("suspicions", {})

    @classmethod
    def from_json(cls, filepath: str | Path) -> "WorldState":
        """Load world state from a JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls(data)

    def to_json(self, filepath: str | Path) -> None:
        """Save current state to a JSON file."""
        with open(filepath, "w") as f:
            json.dump(self._data, f, indent=2)

    @property
    def locations(self) -> dict[str, Any]:
        return self._data["locations"]

    @property
    def items(self) -> dict[str, Any]:
        return self._data["items"]

    @property
    def agents(self) -> dict[str, Any]:
        return self._data["agents"]

    @property
    def relationships(self) -> dict[str, Any]:
        return self._data["relationships"]

    @property
    def suspicions(self) -> dict[str, Any]:
        return self._data["suspicions"]

    def get_relationship_view(self, agent_id: str, other_agent_id: str) -> dict[str, Any]:
        """Return one agent's current relationship view of another."""
        return self._data["relationships"].get(agent_id, {}).get(other_agent_id, {
            "trust": 50,
            "affinity": 50,
            "notes": ""
        })

    def get_suspicion_view(self, agent_id: str, other_agent_id: str) -> int:
        """Return one agent's hidden suspicion score toward another."""
        return int(self._data["suspicions"].get(agent_id, {}).get(other_agent_id, 0))

    # Location operations
    def add_location(
        self,
        loc_id: str,
        name: str,
        description: str,
        connected_to: list[str] | None = None,
        status_effects: list[str] | None = None,
        systems: dict[str, Any] | None = None
    ) -> None:
        """Add a new location to the world."""
        self._data["locations"][loc_id] = {
            "name": name,
            "description": description,
            "connected_to": connected_to or [],
            "status_effects": status_effects or [],
            "systems": systems or {}
        }

    def get_location(self, loc_id: str) -> dict[str, Any] | None:
        """Get location details by ID."""
        return self._data["locations"].get(loc_id)

    def get_location_systems(self, loc_id: str) -> dict[str, Any]:
        """Get the system map for a location."""
        location = self._data["locations"].get(loc_id, {})
        return location.get("systems", {})

    def set_system_status(self, loc_id: str, system_id: str, status: str) -> bool:
        """Update a named system in a location."""
        systems = self.get_location_systems(loc_id)
        if system_id not in systems:
            return False
        systems[system_id]["status"] = status
        return True

    def is_adjacent(self, from_loc: str, to_loc: str) -> bool:
        """Check if two locations are connected."""
        loc = self._data["locations"].get(from_loc)
        if not loc:
            return False
        return to_loc in loc.get("connected_to", [])

    # Item operations
    def add_item(
        self,
        item_id: str,
        name: str,
        location: str,
        description: str = "",
        portable: bool = True,
        owner: str | None = None
    ) -> None:
        """Add a new item to the world."""
        self._data["items"][item_id] = {
            "name": name,
            "location": location,
            "owner": owner,
            "description": description,
            "portable": portable
        }

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        """Get item details by ID."""
        return self._data["items"].get(item_id)

    def find_items_by_location(self, loc_id: str) -> list[dict[str, Any]]:
        """Find all items at a specific location."""
        return [
            {"id": iid, **item}
            for iid, item in self._data["items"].items()
            if item.get("location") == loc_id
        ]

    def find_items_by_owner(self, agent_id: str) -> list[dict[str, Any]]:
        """Find all items owned by an agent."""
        return [
            {"id": iid, **item}
            for iid, item in self._data["items"].items()
            if item.get("owner") == agent_id
        ]

    # Agent state operations
    def set_agent_location(self, agent_id: str, loc_id: str) -> bool:
        """Update an agent's current location."""
        if agent_id not in self._data["agents"]:
            return False
        self._data["agents"][agent_id]["location"] = loc_id
        return True

    def get_agent_location(self, agent_id: str) -> str | None:
        """Get an agent's current location."""
        return self._data["agents"].get(agent_id, {}).get("location")

    def add_item_to_agent_inventory(self, agent_id: str, item_id: str) -> bool:
        """Add an item to an agent's inventory."""
        if agent_id not in self._data["agents"]:
            return False
        if item_id not in self._data["items"]:
            return False
        agents = self._data["agents"]
        items = self._data["items"]

        if item_id not in agents[agent_id].get("inventory", []):
            agents[agent_id]["inventory"].append(item_id)
            items[item_id]["location"] = agent_id
            items[item_id]["owner"] = agent_id
            return True
        return False

    def remove_item_from_agent_inventory(self, agent_id: str, item_id: str) -> bool:
        """Remove an item from an agent's inventory."""
        if agent_id not in self._data["agents"]:
            return False
        agents = self._data["agents"]
        items = self._data["items"]
        agent_location = agents[agent_id].get("location")

        inventory = agents[agent_id].get("inventory", [])
        if item_id in inventory:
            inventory.remove(item_id)
            # When an item is dropped it returns to the agent's current room.
            items[item_id]["owner"] = None
            items[item_id]["location"] = agent_location
            return True
        return False

    def transfer_item_between_agents(self, from_agent_id: str, to_agent_id: str, item_id: str) -> bool:
        """Move an item directly from one agent's inventory to another's."""
        if not self.remove_item_from_agent_inventory(from_agent_id, item_id):
            return False
        return self.add_item_to_agent_inventory(to_agent_id, item_id)

    def register_agent(self, agent_id: str, location: str) -> None:
        """Register a new agent in the world state."""
        self._data["agents"][agent_id] = {
            "location": location,
            "inventory": [],
            "status_effects": []
        }

    # Utility methods for agents to query their environment
    def get_visible_items(self, agent_id: str) -> list[dict[str, Any]]:
        """Get all items visible to an agent (at their current location)."""
        loc = self.get_agent_location(agent_id)
        if not loc:
            return []
        return self.find_items_by_location(loc)

    def get_visible_agents(self, agent_id: str) -> list[str]:
        """Get IDs of all agents at the same location."""
        my_loc = self.get_agent_location(agent_id)
        if not my_loc:
            return []
        return [
            aid for aid, data in self._data["agents"].items()
            if data.get("location") == my_loc and aid != agent_id
        ]

    def get_snapshot_for_agent(self, agent_id: str) -> dict[str, Any]:
        """
        Get a filtered view of the world suitable for an agent's Sense phase.
        This is what gets passed to the LLM - not the entire world state.
        """
        loc = self.get_agent_location(agent_id)
        location_data = self.get_location(loc) if loc else None

        visible_agents = self.get_visible_agents(agent_id)

        return {
            "agent_id": agent_id,
            "current_location": {
                "id": loc,
                **location_data
            } if location_data else None,
            "visible_items": [
                {"id": iid, **item}
                for iid, item in self.items.items()
                if item.get("location") == loc
            ],
            "visible_systems": {
                system_id: dict(system_data)
                for system_id, system_data in self.get_location_systems(loc).items()
            } if loc else {},
            "visible_agents": visible_agents,
            "visible_agent_hands": {
                other_id: [
                    item["name"]
                    for item in self.find_items_by_owner(other_id)
                    if not item.get("hidden")
                ]
                for other_id in visible_agents
            },
            "relationship_impressions": {
                other_id: {
                    **self.get_relationship_view(agent_id, other_id),
                    "suspicion": self.get_suspicion_view(agent_id, other_id)
                }
                for other_id in visible_agents
            },
            "agent_inventory": [
                {"id": iid, **self.items[iid]}
                for iid in self._data["agents"].get(agent_id, {}).get("inventory", [])
                if iid in self.items
            ]
        }

    def __repr__(self) -> str:
        return f"WorldState(locations={len(self.locations)}, items={len(self.items)})"
