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
            "GIVE": self._handle_give,
            "DEMAND": self._handle_demand,
            "LIE": self._handle_lie,
            "READ": self._handle_read,
            "SHOW": self._handle_show,
            "SABOTAGE": self._handle_sabotage,
            "REPAIR": self._handle_repair,
            "WHISPER": self._handle_whisper,
            "CONCEAL": self._handle_conceal,
            "PRODUCE": self._handle_produce,
            "USE": self._handle_use,
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

    def _hand_items(self, agent_id: str) -> list[dict]:
        """Return the agent's non-hidden (in-hand) inventory items."""
        return [i for i in self.world.find_items_by_owner(agent_id) if not i.get("hidden")]

    def _person_items(self, agent_id: str) -> list[dict]:
        """Return the agent's hidden (on-person) inventory items."""
        return [i for i in self.world.find_items_by_owner(agent_id) if i.get("hidden")]

    def _resolve_system_tool_requirement(self, system_data: dict[str, Any], action: str) -> str | None:
        """Return the configured required tool for a system action."""
        action_upper = action.upper()
        if action_upper == "REPAIR":
            return system_data.get("required_tool_repair") or system_data.get("required_tool")
        if action_upper == "SABOTAGE":
            return system_data.get("required_tool_sabotage")
        return None

    def _has_required_hand_tool(self, agent_id: str, required_tool: str) -> tuple[bool, list[str]]:
        """Check whether the agent is visibly holding the required tool."""
        hand = self._hand_items(agent_id)
        holding = [item["name"] for item in hand]
        has_tool = any(
            required_tool.lower() in item["name"].lower() or item["id"] == required_tool
            for item in hand
        )
        return has_tool, holding

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

        # Enforce two-slot inventory (one in hand, one concealed on person)
        hand = self._hand_items(agent.agent_id)
        person = self._person_items(agent.agent_id)

        if matching_item.get("hidden"):
            # Hidden items require a free hand to handle and a free person slot to conceal
            if hand:
                return False, f"Failure: You need a free hand to handle {matching_item['name']}. Drop {hand[0]['name']} first."
            if person:
                return False, f"Failure: You're already concealing something on your person. You can't hide another item."
        else:
            # Regular items go in hand — hand must be free
            if hand:
                return False, f"Failure: Your hand is already full (holding {hand[0]['name']}). Drop it first."

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

    def _handle_use(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle USE action — consume a held item and trigger its effect."""
        hand = self._hand_items(agent.agent_id)
        matching_item = next(
            (item for item in hand if target.lower() in item["name"].lower() or item["id"] == target),
            None
        )
        if not matching_item:
            held = [item["name"] for item in hand]
            return False, f"Failure: '{target}' is not in your hand. Holding: {', '.join(held) if held else 'nothing'}."

        if not matching_item.get("consumable"):
            return False, f"Failure: The {matching_item['name']} is not a consumable item."

        return True, f"Success: You used the {matching_item['name']}."

    def _handle_wait(self, agent, _, __) -> tuple[bool, str]:
        """Handle WAIT action."""
        return True, "You waited patiently for the next cycle."

    @staticmethod
    def _parse_social_target(target: str) -> tuple[str, str] | None:
        """Parse an action target into (item, agent_id)."""
        for separator in ["->", "|", "@", ":"]:
            if separator in target:
                item_part, agent_part = target.split(separator, 1)
                item_name = item_part.strip()
                agent_id = agent_part.strip()
                if item_name and agent_id:
                    return item_name, agent_id
        return None

    def _resolve_visible_agent(self, actor_id: str, target_agent_id: str):
        """Resolve a target agent only if they are currently visible."""
        visible = self.world.get_visible_agents(actor_id)
        if target_agent_id not in visible:
            return None
        return self.world.agents.get(target_agent_id)

    def _handle_give(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle GIVE action: GIVE item -> agent_id."""
        parsed = self._parse_social_target(target)
        if not parsed:
            return False, "Failure: GIVE requires 'item -> agent_id'."

        item_name, target_agent_id = parsed
        if not self._resolve_visible_agent(agent.agent_id, target_agent_id):
            return False, f"Failure: '{target_agent_id}' is not here to receive anything."

        owned_items = self.world.find_items_by_owner(agent.agent_id)
        matching_item = next(
            (item for item in owned_items if item_name.lower() in item["name"].lower() or item["id"] == item_name),
            None
        )
        if not matching_item:
            owned = [item["name"] for item in owned_items]
            return False, f"Failure: You are not carrying '{item_name}'. Carrying: {', '.join(owned) if owned else 'nothing'}."

        # Check receiver has a free hand slot
        receiver_hand = self._hand_items(target_agent_id)
        if receiver_hand:
            return False, f"Failure: {target_agent_id}'s hands are full. They need to drop something first."

        if not self.world.transfer_item_between_agents(agent.agent_id, target_agent_id, matching_item["id"]):
            return False, "Failure: The handoff did not complete."

        return True, f"Success: You gave {matching_item['name']} to {target_agent_id}."

    def _handle_demand(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle DEMAND action: DEMAND item -> agent_id."""
        parsed = self._parse_social_target(target)
        if not parsed:
            return False, "Failure: DEMAND requires 'item -> agent_id'."

        item_name, target_agent_id = parsed
        if not self._resolve_visible_agent(agent.agent_id, target_agent_id):
            return False, f"Failure: '{target_agent_id}' is not here."

        held_items = self.world.find_items_by_owner(target_agent_id)
        matching_item = next(
            (item for item in held_items if item_name.lower() in item["name"].lower() or item["id"] == item_name),
            None
        )
        if not matching_item:
            return False, f"Failure: {target_agent_id} does not appear to be carrying '{item_name}'."

        # Check the demander has a free hand slot to receive
        my_hand = self._hand_items(agent.agent_id)
        if my_hand:
            return False, f"Failure: Your hand is full (holding {my_hand[0]['name']}). Drop it before demanding something."

        if not self.world.transfer_item_between_agents(target_agent_id, agent.agent_id, matching_item["id"]):
            return False, "Failure: The demanded transfer did not complete."

        return True, f"Success: You forced {target_agent_id} to hand over {matching_item['name']}."

    def _handle_lie(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle LIE action as a flagged speech act."""
        if not target or len(target.strip()) < 2:
            return False, "Failure: You can't lie without saying anything."

        return True, f"Success: You lied to everyone in the room: '{target}'."

    def _find_accessible_item(self, agent_id: str, target: str) -> dict | None:
        """Find an item the agent is carrying or can see in their current room."""
        current_loc = self.world.get_agent_location(agent_id)
        candidates = self.world.find_items_by_owner(agent_id)
        if current_loc:
            candidates.extend(self.world.find_items_by_location(current_loc))
        return next(
            (item for item in candidates if target.lower() in item["name"].lower() or item["id"] == target),
            None
        )

    def _fact_id_for_item(self, item: dict) -> str:
        return item.get("fact_id") or f"item:{item['id']}"

    def _handle_read(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle READ action - learn knowledge from an accessible item."""
        if not target or not target.strip():
            return False, "Failure: READ requires an item name."

        matching_item = self._find_accessible_item(agent.agent_id, target)
        if not matching_item:
            return False, f"Failure: You can't access '{target}' to read it."

        knowledge = matching_item.get("knowledge")
        if not knowledge:
            return False, f"Failure: The {matching_item['name']} contains no readable hidden information."

        self.world.remember_fact(
            agent.agent_id,
            self._fact_id_for_item(matching_item),
            knowledge,
            source_item_id=matching_item["id"]
        )
        return True, f"Success: You read the {matching_item['name']}."

    def _handle_show(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle SHOW action: SHOW item -> agent_id."""
        parsed = self._parse_social_target(target)
        if not parsed:
            return False, "Failure: SHOW requires 'item -> agent_id'."

        item_name, target_agent_id = parsed
        if not self._resolve_visible_agent(agent.agent_id, target_agent_id):
            return False, f"Failure: '{target_agent_id}' is not here to show anything."

        matching_item = self._find_accessible_item(agent.agent_id, item_name)
        if not matching_item:
            return False, f"Failure: You can't access '{item_name}' to show it."

        knowledge = matching_item.get("knowledge")
        if not knowledge:
            return False, f"Failure: The {matching_item['name']} has no hidden information to show."

        self.world.remember_fact(
            agent.agent_id,
            self._fact_id_for_item(matching_item),
            knowledge,
            source_item_id=matching_item["id"]
        )
        self.world.remember_fact(
            target_agent_id,
            self._fact_id_for_item(matching_item),
            knowledge,
            source_item_id=matching_item["id"],
            shared_by=agent.agent_id
        )
        return True, f"Success: You showed {matching_item['name']} to {target_agent_id}."

    def _handle_sabotage(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle SABOTAGE action on a local system."""
        if getattr(agent, "archetype", "").lower() != "saboteur":
            return False, "Failure: You are not equipped to perform sabotage."

        current_loc = self.world.get_agent_location(agent.agent_id)
        if not current_loc:
            return False, "Failure: You don't know where you are."

        if self.world.get_visible_agents(agent.agent_id):
            return False, "Failure: Someone else is here. Sabotage would be too obvious."

        systems_here = self.world.get_location_systems(current_loc)
        matching_system_id = None
        for system_id, system_data in systems_here.items():
            system_name = system_data.get("name", system_id)
            if target.lower() in system_name.lower() or system_id == target:
                matching_system_id = system_id
                break

        if not matching_system_id:
            available = [data.get("name", system_id) for system_id, data in systems_here.items()]
            return False, f"Failure: No sabotagable system '{target}' here. Systems: {', '.join(available) if available else 'none'}."

        if systems_here[matching_system_id].get("status") == "BROKEN":
            return False, f"Failure: {matching_system_id} is already broken."

        required_tool = self._resolve_system_tool_requirement(systems_here[matching_system_id], "SABOTAGE")
        if required_tool:
            has_tool, holding = self._has_required_hand_tool(agent.agent_id, required_tool)
            if not has_tool:
                return False, (
                    f"Failure: Sabotaging {systems_here[matching_system_id].get('name', matching_system_id)} "
                    f"requires {required_tool}. You are holding: {', '.join(holding) if holding else 'nothing'}."
                )

        self.world.set_system_status(current_loc, matching_system_id, "BROKEN")
        return True, f"Success: You disabled the {matching_system_id}."

    def _handle_repair(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle REPAIR action on a local system that is down."""
        current_loc = self.world.get_agent_location(agent.agent_id)
        if not current_loc:
            return False, "Failure: You don't know where you are."

        systems_here = self.world.get_location_systems(current_loc)
        matching_system_id = None
        for system_id, system_data in systems_here.items():
            system_name = system_data.get("name", system_id)
            if target.lower() in system_name.lower() or system_id == target:
                matching_system_id = system_id
                break

        if not matching_system_id:
            available = [data.get("name", sid) for sid, data in systems_here.items()]
            return False, f"Failure: No repairable system '{target}' here. Systems: {', '.join(available) if available else 'none'}."

        system_status = systems_here[matching_system_id].get("status", "unknown")
        if system_status not in {"OFFLINE", "BROKEN"}:
            return False, (
                f"Failure: {systems_here[matching_system_id].get('name', matching_system_id)} "
                f"is currently {system_status}, so repair is not needed. Consider another action."
            )

        required_tool = self._resolve_system_tool_requirement(systems_here[matching_system_id], "REPAIR")
        if required_tool:
            has_tool, holding = self._has_required_hand_tool(agent.agent_id, required_tool)
            if not has_tool:
                return False, f"Failure: Repairing {systems_here[matching_system_id].get('name', matching_system_id)} requires {required_tool}. You are holding: {', '.join(holding) if holding else 'nothing'}."

        self.world.set_system_status(current_loc, matching_system_id, "ONLINE")
        return True, f"Success: You repaired the {systems_here[matching_system_id].get('name', matching_system_id)}."

    def _handle_whisper(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle WHISPER action: WHISPER message -> agent_id."""
        parsed = self._parse_social_target(target)
        if not parsed:
            return False, "Failure: WHISPER requires 'message -> agent_id'."

        message, target_agent_id = parsed
        if not message.strip():
            return False, "Failure: You can't whisper nothing."

        if not self._resolve_visible_agent(agent.agent_id, target_agent_id):
            return False, f"Failure: '{target_agent_id}' is not here."

        return True, f"Success: You whispered to {target_agent_id}."

    def _handle_conceal(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle CONCEAL action — move an item from hand to the concealed person slot."""
        hand = self._hand_items(agent.agent_id)
        matching_item = next(
            (item for item in hand if target.lower() in item["name"].lower() or item["id"] == target),
            None
        )
        if not matching_item:
            held = [item["name"] for item in hand]
            return False, f"Failure: '{target}' is not in your hand. Holding: {', '.join(held) if held else 'nothing'}."

        person = self._person_items(agent.agent_id)
        if person:
            return False, f"Failure: You are already concealing {person[0]['name']} on your person."

        self.world.set_item_hidden(matching_item["id"], True)
        return True, f"Success: You concealed the {matching_item['name']} on your person."

    def _handle_produce(self, agent, target: str, action_json: dict[str, Any]) -> tuple[bool, str]:
        """Handle PRODUCE action — move a concealed item from person slot to hand."""
        person = self._person_items(agent.agent_id)
        matching_item = next(
            (item for item in person if target.lower() in item["name"].lower() or item["id"] == target),
            None
        )
        if not matching_item:
            concealed = [item["name"] for item in person]
            return False, f"Failure: '{target}' is not concealed on your person. Concealing: {', '.join(concealed) if concealed else 'nothing'}."

        hand = self._hand_items(agent.agent_id)
        if hand:
            return False, f"Failure: Your hand is already holding {hand[0]['name']}. Drop it first."

        self.world.set_item_hidden(matching_item["id"], False)
        return True, f"Success: You produced the {matching_item['name']}."

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
