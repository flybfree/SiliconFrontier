"""
ActionParser - The System Arbiter of Silicon Frontier

Validates and executes agent actions against the WorldState, enforcing
deterministic boundaries and preventing hallucinated abilities.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .worldstate import WorldState


class ActionParser:
    """
    Validates agent actions against world physics and updates state accordingly.

    This is the "Dungeon Master" that prevents agents from:
    - Moving to non-existent locations
    - Picking up items they can't reach
    - Claiming ownership through words alone
    - Performing impossible actions
    """

    def __init__(self, world_state):
        """
        Initialize the action parser with a reference to the world state.

        Args:
            world_state: WorldState instance providing ground truth
        """
        self.world = world_state

    def execute(self, agent, action_json: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate and execute an agent's action.

        Args:
            agent: FrontierAgent instance taking the action
            action_json: Parsed JSON from LLM with 'action' and 'action_target'

        Returns:
            Tuple of (success: bool, feedback_message: str)
        """
        action = action_json.get("action", "").upper()
        target = action_json.get("action_target", "")

        # Route to appropriate handler
        handlers = {
            "MOVE": self._handle_move,
            "SAY": self._handle_say,
            "PICKUP": self._handle_pickup,
            "DROP": self._handle_drop,
            "WAIT": self._handle_wait
        }

        handler = handlers.get(action)
        if handler:
            return handler(agent, target, action_json)

        return False, f"Failure: Unknown action '{action}'. Valid actions: {', '.join(agent.VALID_ACTIONS)}"

    def _handle_move(self, agent, target: str, _) -> tuple[bool, str]:
        """Handle MOVE action."""
        current_loc = self.world.get_agent_location(agent.agent_id)
        if not current_loc:
            return False, f"Failure: You don't know where you are."

        # Check if destination exists
        dest_info = self.world.get_location(target)
        if not dest_info:
            return False, f"Failure: '{target}' is not a valid location."

        # Check adjacency
        if not self.world.is_adjacent(current_loc, target):
            connected = [loc_id for loc_id in self.world.locations[current_loc].get("connected_to", [])]
            return (
                False,
                f"Failure: '{target}' is not accessible from '{current_loc}'. "
                f"Connected locations: {', '.join(connected) if connected else 'none'}."
            )

        # Execute move
        self.world.set_agent_location(agent.agent_id, target)
        return True, f"Success: You moved to {target}."

    def _handle_say(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle SAY action - returns success but actual broadcasting is done by Orchestrator."""
        # Validate the message isn't empty
        if not target or len(target.strip()) < 2:
            return False, "Failure: You can't say nothing."

        return True, f"Success: You said '{target}' to everyone in the room."

    def _handle_pickup(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle PICKUP action."""
        current_loc = self.world.get_agent_location(agent.agent_id)
        if not current_loc:
            return False, "Failure: You don't know where you are."

        # Find the item by name (partial match allowed)
        items_here = self.world.find_items_by_location(current_loc)
        matching_item = None

        for item in items_here:
            if target.lower() in item["name"].lower() or item["id"] == target:
                matching_item = item
                break

        if not matching_item:
            available = [item["name"] for item in items_here]
            return (
                False,
                f"Failure: You don't see '{target}' here. "
                f"You see: {', '.join(available) if available else 'nothing'}."
            )

        # Check if portable
        if not matching_item.get("portable", True):
            return False, f"Failure: The {matching_item['name']} is too heavy to move."

        # Execute pickup
        self.world.add_item_to_agent_inventory(agent.agent_id, matching_item["id"])
        return True, f"Success: You are now holding the {matching_item['name']}."

    def _handle_drop(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle DROP action."""
        # Find item in inventory by name (partial match)
        items_here = self.world.find_items_by_owner(agent.agent_id)
        matching_item = None

        for item in items_here:
            if target.lower() in item["name"].lower() or item["id"] == target:
                matching_item = item
                break

        if not matching_item:
            owned = [item["name"] for item in items_here]
            return (
                False,
                f"Failure: You aren't holding '{target}'. "
                f"You are carrying: {', '.join(owned) if owned else 'nothing'}."
            )

        # Execute drop
        self.world.remove_item_from_agent_inventory(agent.agent_id, matching_item["id"])
        return True, f"Success: You dropped the {matching_item['name']}."

    def _handle_wait(self, agent, _, __) -> tuple[bool, str]:
        """Handle WAIT action."""
        return True, "You waited patiently for the next cycle."

    # Validation utilities for Orchestrator to use before executing actions
    @staticmethod
    def validate_move(current_loc: str, target: str, world_state: WorldState) -> tuple[bool, str]:
        """Pre-validate a MOVE action without executing."""
        if not world_state.get_location(target):
            return False, f"Location '{target}' does not exist."

        if not world_state.is_adjacent(current_loc, target):
            return False, f"'{target}' is not connected to '{current_loc}'."

        return True, ""

    @staticmethod
    def validate_pickup(agent_id: str, item_name: str, world_state: WorldState) -> tuple[bool, str]:
        """Pre-validate a PICKUP action without executing."""
        current_loc = world_state.get_agent_location(agent_id)
        if not current_loc:
            return False, "Agent has no known location."

        items_here = world_state.find_items_by_location(current_loc)
        matching_item = None

        for item in items_here:
            if item_name.lower() in item["name"].lower():
                matching_item = item
                break

        if not matching_item:
            available = [item["name"] for item in items_here]
            return False, f"Item '{item_name}' not found. Available: {', '.join(available)}."

        if not matching_item.get("portable", True):
            return False, f"'{matching_item['name']}' is not portable."

        return True, ""
