"""
FrontierAgent - The Cognitive Unit of Silicon Frontier

Represents an autonomous entity that perceives its environment, reasons about
its goals, and takes actions through a local LLM inference engine.
"""

import json
import re
import traceback
from typing import Any
from openai import OpenAI

# `settings` is imported lazily inside the functions that need it (this module
# is loaded both as a bare top-level module and as part of the `src` package
# via src/__init__.py in the frozen launcher — a module-level bare import only
# resolves in the former context).

# Import settings lazily to avoid circular imports at module load time.
# The defaults are resolved inside the function bodies, not at class definition time.


class FrontierAgent:
    """
    An autonomous agent with personality, memory, and goal-directed behavior.

    Each agent operates on the Sense -> Think -> Act -> Reflect cycle:
    1. SENSE: Filters world state to create a subjective view
    2. THINK: LLM generates internal monologue reasoning about goals
    3. ACT: LLM outputs a JSON action from a constrained set
    4. REFLECT: Periodically summarizes memory into long-term storage
    """

    # Valid actions an agent can take
    VALID_ACTIONS = ["MOVE", "SAY", "WHISPER", "PICKUP", "DROP", "USE", "GIVE", "DEMAND", "LIE", "READ", "SHOW", "SABOTAGE", "REPAIR", "CONCEAL", "PRODUCE", "STOW", "READY", "ASSEMBLE", "WAIT"]
    VALID_EMOTIONAL_STATES = ["Calm", "Alert", "Anxious", "Fearful", "Angry", "Hopeful", "Suspicious", "Confident", "Resigned", "Determined", "Neutral"]
    VALID_EMOTIONAL_STATE_FALLBACK = "Neutral"
    RESPONSE_SCHEMA_NAME = "silicon_frontier_agent_turn"
    STRUCTURED_STATUS_STRUCTURED = "structured_ok"
    STRUCTURED_STATUS_FALLBACK = "structured_fallback"
    STRUCTURED_STATUS_PARSE_FALLBACK = "structured_parse_fallback"
    STRUCTURED_STATUS_DISABLED = "structured_disabled"
    STRUCTURED_STATUS_VALIDATED = "structured_validated"
    STRUCTURED_STATUS_VALIDATED_CORRECTED = "structured_validated_corrected"
    STRUCTURED_STATUS_MODEL_FALLBACK = "model_error_fallback"
    _INVENTORY_LABEL_SUFFIX = re.compile(r"\s*\[(?:protected|recipe material|material|consumable|disposable)\]\s*", re.IGNORECASE)
    DEFAULT_CONDITION = {
        "health": 100,
        "stress": 0,
        "fatigue": 0,
        "morale": 50
    }

    _ONLINE_NEGATIVE_TERMS = (
        "fail", "failed", "failing", "failure", "offline", "broken", "degraded",
        "malfunction", "malfunctioning", "down", "not online", "unstable"
    )
    _NON_ONLINE_POSITIVE_TERMS = (
        "online", "operational", "fully operational", "stable", "working", "functional"
    )

    def __init__(
        self,
        agent_id: str,
        name: str,
        persona: str,
        secret_goal: str,
        role: str | None = None,
        is_saboteur: bool | None = None,
        perception: int = 50,
        condition: dict[str, Any] | None = None,
        llm_base_url: str | None = None,
        llm_model: str | None = None,
        social_critic_base_url: str | None = None,
        social_critic_model: str | None = None,
        strategic_reasoning_base_url: str | None = None,
        strategic_reasoning_model: str | None = None,
        enable_structured_output: bool = False,
        api_key: str | None = None,
        llm_timeout_seconds: float | None = None
    ):
        """
        Initialize an agent with its cognitive profile.

        Args:
            agent_id: Unique identifier for the agent (e.g., "agent_001")
            name: Display name of the agent (e.g., "Captain Miller")
            persona: Description of personality and role
            secret_goal: Hidden motivation that drives conflict/behavior
            llm_base_url: URL of local OpenAI-compatible inference engine
            llm_model: Model name to use for inference
            social_critic_base_url: Optional OpenAI-compatible endpoint for witness critics
            social_critic_model: Optional fast model for witness critics
            api_key: API key (usually not needed for local models)
            llm_timeout_seconds: Per-request timeout for LLM calls (seconds)
        """
        # Resolve settings with layered priority: explicit arg > env var > settings.json > defaults
        from settings import (
            get_api_key,
            get_llm_base_url,
            get_llm_model,
            get_llm_timeout_seconds,
            get_social_critic_base_url,
            get_social_critic_model,
            get_strategic_reasoning_base_url,
            get_strategic_reasoning_model,
        )

        resolved_llm_base_url = get_llm_base_url(llm_base_url)
        resolved_llm_model = get_llm_model(llm_model)
        resolved_api_key = get_api_key(api_key)
        resolved_timeout = get_llm_timeout_seconds(llm_timeout_seconds)
        resolved_social_critic_base_url = get_social_critic_base_url(social_critic_base_url)
        resolved_social_critic_model = get_social_critic_model(social_critic_model)
        resolved_strategic_base_url = get_strategic_reasoning_base_url(strategic_reasoning_base_url)
        resolved_strategic_model = get_strategic_reasoning_model(strategic_reasoning_model)

        self.agent_id = agent_id
        self.name = name
        self.persona = persona
        self.secret_goal = secret_goal
        self.role = role or "crew member"
        # A public role describes an agent's station job.  Saboteur is a hidden
        # assignment which controls whether destructive tactics are appropriate.
        # Keep the goal-based fallback for scenarios saved before this field
        # existed, so old scenarios do not silently lose their antagonist.
        self.is_saboteur = (
            bool(is_saboteur)
            if is_saboteur is not None
            else self._infer_saboteur_assignment()
        )
        self.perception = self._clamp_0_100(perception)
        self.condition = self._normalize_condition(condition)
        self.enable_structured_output = enable_structured_output

        # Memory systems
        self.memory_buffer: list[str] = []  # Short-term, last N events
        self.long_term_memory: str = "I just arrived at the Silicon Frontier station."

        # LLM client configuration
        self.client = OpenAI(
            base_url=resolved_llm_base_url,
            api_key=resolved_api_key,
            timeout=resolved_timeout
        )
        self.llm_base_url = resolved_llm_base_url
        self.llm_model = resolved_llm_model
        self.social_critic_client = OpenAI(
            base_url=resolved_social_critic_base_url,
            api_key=resolved_api_key,
            timeout=resolved_timeout,
        )
        self.social_critic_base_url = resolved_social_critic_base_url
        self.social_critic_model = resolved_social_critic_model
        self.strategic_client = OpenAI(
            base_url=resolved_strategic_base_url,
            api_key=resolved_api_key,
            timeout=resolved_timeout,
        )
        self.strategic_reasoning_base_url = resolved_strategic_base_url
        self.strategic_reasoning_model = resolved_strategic_model
        self.strategic_plan: dict[str, Any] = {}
        self.last_strategic_review_cycle: int | None = None
        self.last_strategic_trigger: str | None = None
        self.last_model_error: dict[str, str] | None = None
        self.last_social_critic_error: dict[str, str] | None = None
        self.last_strategic_error: dict[str, str] | None = None
        self.last_reflection_result: dict[str, str] | None = None

        # Emotional state tracking (for observation)
        self.emotional_state: str = "Neutral"
        self.last_structured_output_status: str | None = None

        # Goal momentum: agent's sense of whether they're making progress
        self.goal_momentum: str = "stalled"
        # Successful evidence/tool interactions are remembered separately from
        # prose memory so a model cannot mistake a repeated identical effect for
        # new progress on every subsequent turn.
        self.completed_effects: dict[str, str] = {}
        self.progress_events: list[str] = []
        self.blocked_targets: dict[str, dict[str, Any]] = {}

        # Pending drop obligation: set by item data for clues that must be returned.
        # Agent must DROP this item before taking any other action.
        self.pending_drop: str | None = None        # item id
        self.pending_drop_name: str | None = None   # item name (for prompts)

    @staticmethod
    def _clamp_0_100(value: Any) -> int:
        """Clamp a numeric value to the valid 0-100 range used by condition/perception fields."""
        return max(0, min(100, int(value)))

    @classmethod
    def _normalize_condition(cls, condition: dict[str, Any] | None) -> dict[str, int]:
        """Return a complete, clamped condition block for an agent."""
        normalized = dict(cls.DEFAULT_CONDITION)
        if isinstance(condition, dict):
            for key in normalized:
                if key in condition:
                    normalized[key] = cls._clamp_0_100(condition[key])
        return normalized

    def condition_text(self) -> str:
        """Return condition as compact prompt text."""
        return ", ".join(f"{key}={value}" for key, value in self.condition.items())

    def _condition_guidance(self) -> str:
        """Return behavioral nudges for extreme condition values."""
        parts = []
        if self.condition.get("health", 100) < 30:
            parts.append("critically low health — avoid risky confrontations")
        if self.condition.get("stress", 0) > 70:
            parts.append("high stress — prone to impulsive decisions")
        if self.condition.get("fatigue", 0) > 80:
            parts.append("severe fatigue — physical actions feel costly; prefer social or passive moves")
        morale = self.condition.get("morale", 50)
        if morale < 25:
            parts.append("very low morale — you question whether your goal is achievable")
        elif morale > 80:
            parts.append("high morale — you feel capable and driven")
        return "; ".join(parts)

    def adjust_condition(self, **deltas: int) -> dict[str, int]:
        """Apply clamped condition deltas and return changed fields."""
        changed = {}
        for key in self.DEFAULT_CONDITION:
            delta = int(deltas.get(key, 0) or 0)
            if not delta:
                continue
            before = self.condition.get(key, self.DEFAULT_CONDITION[key])
            after = self._clamp_0_100(before + delta)
            self.condition[key] = after
            if after != before:
                changed[key] = after - before
        return changed

    # Preset anchors for label matching (mirrors library/relationship_presets.json)
    _RELATIONSHIP_PRESETS = [
        ("hostile",     14, 12, 70),
        ("distrustful", 28, 32, 38),
        ("rivals",      35, 28, 22),
        ("suspicious",  42, 38, 55),
        ("neutral",     50, 50,  0),
        ("unknown",     50, 50,  0),
        ("colleagues",  62, 58,  0),
        ("deferential", 72, 62,  0),
        ("old_friends", 82, 88,  0),
    ]

    @staticmethod
    def _relationship_label(trust: int, affinity: int, suspicion: int) -> str:
        """Return the name of the closest relationship preset for these values."""
        best_label, best_dist = "neutral", float("inf")
        for label, pt, pa, ps in FrontierAgent._RELATIONSHIP_PRESETS:
            dist = (trust - pt) ** 2 + (affinity - pa) ** 2 + (suspicion - ps) ** 2
            if dist < best_dist:
                best_dist, best_label = dist, label
        return best_label

    def sense(self, world_snapshot: dict[str, Any]) -> str:
        """
        Generate a subjective view of the world for the agent.

        This filters the objective world state into what this specific
        agent can perceive - creating a "subjective truth."

        Args:
            world_snapshot: Filtered world data from WorldState.get_snapshot_for_agent()

        Returns:
            Formatted string describing current situation for LLM prompt
        """
        from settings import DEFAULT_RELATIONSHIP_TRUST, DEFAULT_RELATIONSHIP_AFFINITY

        loc = world_snapshot["current_location"]
        location_name = loc.get("name", "Unknown") if loc else "Unknown"
        location_desc = loc.get("description", "") if loc else ""
        connected = loc.get("connected_to", []) if loc else []
        locations = world_snapshot.get("locations", {})
        exit_labels = []
        for loc_id in connected:
            dest = locations.get(loc_id, {})
            required = dest.get("requires_item") or dest.get("requires_items")
            if isinstance(required, list):
                required_text = ", ".join(str(item) for item in required)
            else:
                required_text = str(required) if required else ""
            suffix = f" (requires: {required_text})" if required_text else ""
            exit_labels.append(f"{loc_id}{suffix}")
        exits_str = ", ".join(exit_labels) if exit_labels else "none"
        location_effects = loc.get("status_effects", []) if loc else []
        location_effects_str = ", ".join(location_effects) if location_effects else "None"

        visible_items = [item["name"] for item in world_snapshot["visible_items"]]
        items_str = ", ".join(visible_items) if visible_items else "None"

        contested_held = [item["name"] for item in world_snapshot["agent_inventory"] if item.get("contested")]
        contested_visible = [item["name"] for item in world_snapshot["visible_items"] if item.get("contested")]
        visible_systems = [
            f"{system_id} ({system_data.get('status', 'unknown')})"
            for system_id, system_data in world_snapshot.get("visible_systems", {}).items()
        ]
        systems_str = ", ".join(visible_systems) if visible_systems else "None"
        abnormal_systems = world_snapshot.get("abnormal_systems", [])
        abnormal_system_lines = [
            f"{entry.get('name', entry.get('system_id', 'unknown'))} in {entry.get('location_name', entry.get('location_id', 'Unknown'))} "
            f"is {entry.get('status', 'unknown')}"
            for entry in abnormal_systems
        ]
        abnormal_systems_str = "\n".join(f"- {line}" for line in abnormal_system_lines) if abnormal_system_lines else "- None"
        known_map = world_snapshot.get("known_map", {})
        known_map_lines = []
        for loc_id, map_data in sorted(known_map.items()):
            state = "explored" if map_data.get("explored") else "mapped but unexplored"
            exits = ", ".join(map_data.get("exits", [])) or "no known exits"
            known_map_lines.append(f"- {map_data.get('name', loc_id)} ({loc_id}; {state}; exits: {exits})")
        known_map_str = "\n".join(known_map_lines) if known_map_lines else "- Only your current surroundings are known."
        known_system_lines = []
        for system in world_snapshot.get("known_systems", []):
            route = system.get("route", [])
            route_text = " -> ".join(route) if route else "route not yet known"
            known_system_lines.append(
                f"- {system.get('name', system.get('system_id', 'unknown'))} in "
                f"{system.get('location_name', system.get('location_id', 'unknown'))} "
                f"is last known {system.get('status', 'unknown')} (route: {route_text})"
            )
        known_systems_str = "\n".join(known_system_lines) if known_system_lines else "- No systems discovered outside your current room."

        agent_inventory = world_snapshot.get("visible_agent_inventory", {})
        nearby_agent_parts = []
        for aid in world_snapshot["visible_agents"]:
            carried = agent_inventory.get(aid, [])
            carried_str = ", ".join(f"{entry['name']} ({entry['slot']})" for entry in carried)
            nearby_agent_parts.append(f"'{aid}' ({carried_str or 'no visible items'})")
        agents_str = ", ".join(nearby_agent_parts) if nearby_agent_parts else "no one"
        relationship_lines = []
        for other_id, rel in world_snapshot.get("relationship_impressions", {}).items():
            label = self._relationship_label(rel.get("trust", DEFAULT_RELATIONSHIP_TRUST), rel.get("affinity", DEFAULT_RELATIONSHIP_AFFINITY), rel.get("suspicion", 0))
            notes = rel.get("notes", "") or ""
            notes_part = f" — {notes}" if notes else ""
            display_name = rel.get("name", other_id)
            relationship_lines.append(f"{display_name}: {label}{notes_part}")
        relationship_str = "\n".join(relationship_lines) if relationship_lines else "No established impressions yet."

        recent_events = self.memory_buffer[-5:] if self.memory_buffer else ["No recent events"]
        events_str = ". ".join(recent_events)
        known_facts = world_snapshot.get("known_facts", [])
        known_fact_lines = [f"- {fact.get('text', '')}" for fact in known_facts[-5:] if fact.get("text")]
        known_facts_str = "\n".join(known_fact_lines) if known_fact_lines else "- None"
        facilities = world_snapshot.get("facilities", [])
        facilities_str = ", ".join(facilities) if facilities else "None"
        recipe_lines = []
        for recipe in world_snapshot.get("available_recipes", []):
            readiness = "materials unavailable"
            if recipe.get("craftable_now"):
                readiness = "READY TO ASSEMBLE NOW"
            elif recipe.get("requires_free_hand"):
                readiness = "materials ready — free your hand first"
            elif recipe.get("missing_materials"):
                missing = ", ".join(
                    f"{material} x{quantity}"
                    for material, quantity in recipe["missing_materials"].items()
                )
                readiness = f"missing: {missing}"
            recipe_lines.append(
                f"- {recipe.get('id')}: {recipe.get('name', recipe.get('id'))} "
                f"(materials: {recipe.get('materials', {})}; {readiness})"
            )
        recipes_str = "\n".join(recipe_lines) if recipe_lines else "- None"

        contested_lines = ""
        if contested_held:
            contested_lines += f"You are holding contested resource(s): {', '.join(contested_held)}. Others may want these.\n"
        if contested_visible:
            contested_lines += f"Contested resource(s) here: {', '.join(contested_visible)}. These are valuable and others may seek them.\n"

        # Synthesize solitude + system state into explicit tactical conditions so the
        # model doesn't have to connect separate lines mid-prompt.
        visible_sys_map = world_snapshot.get("visible_systems", {})
        alone = not world_snapshot["visible_agents"]
        tactical_parts = []
        if alone:
            sabotageable = [
                f"{sid} ({sd.get('status', 'ONLINE')})"
                for sid, sd in visible_sys_map.items()
                if sd.get("status", "ONLINE") != "BROKEN"
            ]
            if sabotageable:
                tactical_parts.append(
                    f"You are unobserved. Sabotageable systems here: {', '.join(sabotageable)}."
                )
                if self._is_saboteur():
                    tactical_parts.append(
                        "Priority opportunity: your disruptive goal and an unobserved local system align. Prefer SABOTAGE of one listed local system over relocating to a remote target unless a concrete immediate constraint makes sabotage impossible."
                    )
            else:
                tactical_parts.append("You are unobserved this turn.")
        elif self._is_saboteur():
            witnessed_targets = [
                f"{sid} ({sd.get('status', 'ONLINE')})"
                for sid, sd in visible_sys_map.items()
                if sd.get("status", "ONLINE") != "BROKEN"
            ]
            if witnessed_targets:
                tactical_parts.append(
                    f"Witnessed sabotage opportunity: {', '.join(witnessed_targets)}. Sabotage here is conspicuous and likely to fail. Consider a cover action or MOVE through a listed exit to seek an unobserved opportunity before trying again."
                )
        if self._is_saboteur() and not any("Priority opportunity:" in part for part in tactical_parts):
            remote_targets = [
                system for system in world_snapshot.get("known_systems", [])
                if system.get("location_id") != (loc.get("id") if loc else None)
                and system.get("status", "ONLINE") != "BROKEN"
                and system.get("route")
            ]
            if remote_targets:
                target = min(remote_targets, key=lambda system: len(system.get("route", [])))
                tactical_parts.append(
                    f"Known alternative: {target.get('name', target.get('system_id'))} is reachable via "
                    f"{' -> '.join(target['route'])}. You may pursue it, or explore an unvisited listed exit to discover new opportunities."
                )
        repairable = [
            f"{sid} ({sd.get('status', 'unknown')})"
            for sid, sd in visible_sys_map.items()
            if sd.get("status", "ONLINE") in {"OFFLINE", "BROKEN", "DEGRADED"}
        ]
        if repairable:
            tactical_parts.append(f"Systems here that need repair: {', '.join(repairable)}.")
        tactical_block = ("\nTactical conditions:\n" + "\n".join(f"- {p}" for p in tactical_parts) + "\n") if tactical_parts else ""

        return (
            f"Location: {location_name}\n"
            f"{location_desc}\n\n"
            f"Verified station telemetry below is authoritative for this turn.\n"
            f"Exits (valid MOVE targets): {exits_str}\n"
            f"Location effects: {location_effects_str}\n"
            f"Items here: {items_str}\n"
            f"Fabrication facilities here: {facilities_str}\n"
            f"Recipes available here:\n{recipes_str}\n"
            f"Systems here: {systems_str}\n"
            f"Known map:\n{known_map_str}\n"
            f"Known discovered systems:\n{known_systems_str}\n"
            f"Known systems needing attention:\n{abnormal_systems_str}\n"
            f"Other agents present: {agents_str}\n"
            f"{contested_lines}"
            f"{tactical_block}"
            f"\nYour current impressions of others:\n{relationship_str}\n\n"
            f"Known private facts:\n{known_facts_str}\n\n"
            f"Recent Events: {events_str}"
        )

    def _build_system_prompt(self, world_snapshot: dict[str, Any]) -> str:
        """Construct the master system prompt for this agent."""
        from settings import DEFAULT_RELATIONSHIP_TRUST, DEFAULT_RELATIONSHIP_AFFINITY

        slots = {"hand": [], "visible": [], "concealed": []}
        for item in world_snapshot["agent_inventory"]:
            slot = str(item.get("inventory_slot", "concealed" if item.get("hidden") else "hand"))
            slots.setdefault(slot, []).append(item["name"])
        def labeled(items: list[str]) -> str:
            return ", ".join(
                f"{item['name']} [{self._inventory_priority_label(item, world_snapshot)}]"
                for item in world_snapshot["agent_inventory"]
                if item["name"] in items
            ) or "empty"

        inventory_str = f"In hand: {labeled(slots['hand'])} | Visible: {labeled(slots['visible'])} | Concealed: {labeled(slots['concealed'])}"
        affordance_lines = [
            f"- {item['name']} (bare action target: {item['name']}): {self._item_affordance(item, world_snapshot)}"
            for item in world_snapshot["agent_inventory"]
        ]
        affordance_text = "\n".join(affordance_lines) or "- No carried items."
        tool_lines = []
        for item in world_snapshot["agent_inventory"]:
            capabilities = item.get("tool", {}).get("capabilities", [])
            if capabilities:
                tool_lines.append(f"- {item['name']}: {', '.join(str(capability) for capability in capabilities)}")
        tool_capabilities = "\n".join(tool_lines) if tool_lines else "- None"
        nearby_agents = world_snapshot["visible_agents"]
        visible_systems = world_snapshot.get("visible_systems", {})
        abnormal_systems = world_snapshot.get("abnormal_systems", [])
        relationship_impressions = world_snapshot.get("relationship_impressions", {})
        relationship_block = []
        for other_id, rel in relationship_impressions.items():
            label = self._relationship_label(rel.get("trust", DEFAULT_RELATIONSHIP_TRUST), rel.get("affinity", DEFAULT_RELATIONSHIP_AFFINITY), rel.get("suspicion", 0))
            notes = rel.get("notes", "") or ""
            notes_part = f" — {notes}" if notes else ""
            display_name = rel.get("name", other_id)
            relationship_block.append(f"- {display_name}: {label}{notes_part}")
        relationship_text = "\n".join(relationship_block) if relationship_block else "- No one nearby yet."
        systems_block = []
        for system_id, system_data in visible_systems.items():
            systems_block.append(
                f"- {system_id}: status={system_data.get('status', 'unknown')}, description={system_data.get('description', '') or 'none'}"
                f"{self._system_requirement_text(system_data)}"
            )
        systems_text = "\n".join(systems_block) if systems_block else "- No systems of note here."
        abnormal_system_block = []
        for system_data in abnormal_systems:
            abnormal_system_block.append(
                f"- {system_data.get('name', system_data.get('system_id', 'unknown'))} "
                f"at {system_data.get('location_name', system_data.get('location_id', 'Unknown'))}: "
                f"status={system_data.get('status', 'unknown')}, "
                f"description={system_data.get('description', '') or 'none'}"
                f"{self._system_requirement_text(system_data)}"
            )
        abnormal_system_text = "\n".join(abnormal_system_block) if abnormal_system_block else "- No non-ONLINE systems known."
        condition_guidance = self._condition_guidance()
        condition_line = (
            f"health={self.condition.get('health', 100)}, stress={self.condition.get('stress', 0)}, "
            f"fatigue={self.condition.get('fatigue', 0)}, morale={self.condition.get('morale', 50)}"
        )
        if condition_guidance:
            condition_line += f" [{condition_guidance}]"

        momentum_guidance = {
            "advancing": "You are making progress — maintain your approach and stay opportunistic.",
            "stalled": "You are stalled — try something bolder or more direct rather than repeating the same cautious pattern.",
            "setback": "You have suffered a setback — regroup, reassess who you can trust, and look for a new angle.",
        }.get(self.goal_momentum, "")
        strategic_plan_text = self._strategic_plan_text()
        completed_effects = getattr(self, "completed_effects", {})
        completed_effects_text = "\n".join(
            f"- {key} ({state})"
            for key, state in list(completed_effects.items())[-6:]
        ) or "- None"
        legal_steps = self._legal_next_steps(world_snapshot)
        legal_steps_text = "\n".join(f"- {step}" for step in legal_steps) or "- No deterministic priority; choose a lawful action that advances your goal."
        blocked_targets_text = "\n".join(
            f"- {target}: {entry.get('reason', 'temporarily blocked')} ({entry.get('turns', 0)} turn(s) remaining)"
            for target, entry in getattr(self, "blocked_targets", {}).items()
        ) or "- None"

        return f"""You are {self.name}, the {self.role} aboard the "Silicon Frontier" research station.

YOUR IDENTITY
Persona: {self.persona}
Secret Motivation: {self.secret_goal}
Current Strategic Plan: {strategic_plan_text}
Condition: {condition_line}
Current Inventory: {inventory_str}
Item affordances (use the bare item name shown before the colon; never include a bracketed inventory label in an action target):
{affordance_text}
Fabricated Tool Capabilities:
{tool_capabilities}
Current Emotional State: {self.emotional_state} — let this genuinely color your reasoning, tone, and choices.

THE SIMULATION RULES
- The World is Discrete: You can only interact with things in your current location. To go elsewhere, you must use the MOVE command.
- Movement: You can only MOVE to locations listed under "Exits (valid MOVE targets)" in your situation report. Do not attempt to move anywhere else.
- Inventory: You have three slots — one item in hand, one visibly carried item, and one concealed item. Other agents can see your hand and visible slots, but never the concealed slot. You must have an empty hand to USE, REPAIR, or SABOTAGE with an item. STOW moves hand -> visible; READY moves visible -> hand; CONCEAL moves hand -> concealed; PRODUCE moves concealed -> hand. Never READY a concealed item — PRODUCE it instead.
- Capacity: Labels identify protected repair/access/evidence items, useful crafting materials, and disposable items. When all slots are full, do not chase a new item unless it is more useful than a disposable carried item. Never drop a protected item merely to make room.
- Completed effects: If a tool, terminal, or clue already gave you its result and the relevant system status has not changed, do not repeat it. Advance by moving, sharing the finding, pursuing a different target, crafting, or taking the next goal step.
- Persistence: Your memories are long-term. Refer to previous events to build trust or hold grudges.
- Truth Constraint: Do NOT invent items or people that are not in your "Current Situation" report.
- Telemetry Constraint: Treat the listed system statuses as the authoritative truth for this turn.
- Outcome Constraint: An inspection establishes only the exact telemetry or evidence returned in its result. It does not degrade, repair, or otherwise alter a system unless the result explicitly says it did. Never claim a hidden percentage change, override, or system effect that the simulation has not reported.
- If a system is shown as ONLINE, do not describe it in your reasoning as failed, offline, broken, degraded, or malfunctioning.
- If you suspect tampering despite an ONLINE status, frame that as suspicion about intent or risk, not as a current failure fact.
- Interaction: You can talk to other agents in the same room using SAY, WHISPER, GIVE, DEMAND, or SHOW.
- Hidden information: PICKUP moves an item; READ learns an item's hidden `knowledge`; SHOW shares that knowledge with another agent in the room.

SOCIAL ANALYSIS
- Who is in the room with you? {', '.join(nearby_agents) if nearby_agents else 'No one'}
- What is your current vibe toward them?
{relationship_text}
- Based on their past actions, what do you think their secret goal might be?
- Does their current action align with what you know about them?

SYSTEMS IN THIS LOCATION
{systems_text}

KNOWN NON-ONLINE SYSTEMS ACROSS THE STATION
{abnormal_system_text}

SYSTEM DECISION RULES
- Choose REPAIR only for a system whose visible status is DEGRADED, OFFLINE, or BROKEN.
- A DEGRADED system is a preventive recovery priority. An OFFLINE or BROKEN system is a critical recovery priority. If you can directly advance either repair, do that before optional conversation, observation, or evidence gathering.
- SABOTAGE is different from REPAIR: an ONLINE or DEGRADED system can be sabotaged if it is visible here.
- Do not choose SABOTAGE for a system whose visible status is already BROKEN.
- If witnesses are present, preserve sabotage tools and relocate or prepare them; do not discard sabotage components merely because sabotage is blocked.
- If a system lists `repair_tool=...`, you must be holding that tool in your hand to REPAIR it.
- If a system lists `sabotage_tool=...`, you must be holding that tool in your hand to SABOTAGE it.
- If the tool for the chosen system action is not listed, no tool is required; the action still requires a valid local target.
- Do not claim a system is failing unless that status is shown in the telemetry above.
- You may ASSEMBLE only a listed recipe at a listed fabrication facility. This consumes its materials and creates a real in-world tool; do not invent recipes or tool effects.
- When a listed recipe says `READY TO ASSEMBLE NOW` and its tool would advance your goal, prefer ASSEMBLE over repeatedly inspecting, waiting, or collecting unrelated materials. When its materials are ready but your hand is occupied, take the indicated slot-management step first.
- For a fabricated tool with a listed capability target, use `USE tool name -> exact system ID`. Tools without a target-aware capability still use `USE tool name`.

ITEM TRANSFER RULES
- DEMAND means taking an item from another visible agent. Do not DEMAND an item you already hold.
- Only choose DEMAND for an item currently shown in that other agent's visible hand.
- GIVE means handing over an item you currently hold.

YOUR KNOWLEDGE SO FAR
Long-term memories: {self.long_term_memory}
Completed effects still current (do not repeat unless the relevant state changes):
{completed_effects_text}
Recommended legal next steps (choose another action only when it is more goal-relevant):
{legal_steps_text}
Recently blocked targets (do not retry until access or world state changes):
{blocked_targets_text}
Your current sense of progress toward your secret goal: {self.goal_momentum}. {momentum_guidance}

{f"""URGENT — ITEM OBLIGATION
You just read the contents of the {self.pending_drop_name}. It contains sensitive information.
You MUST return it — your action this turn MUST be: DROP {self.pending_drop_name}
You cannot move or take any other action until you have put it back.
""" if self.pending_drop else ""}BEFORE YOU ACT
{f"You are alone. No one will witness your actions here." if not nearby_agents else f"{', '.join(nearby_agents)} {'is' if len(nearby_agents) == 1 else 'are'} watching. Consider whether you would act differently if you were alone."}

OUTPUT FORMAT
You must respond strictly in JSON format with this structure:
{{
  "internal_monologue": "A detailed thought process analyzing your secret goal vs. the situation. Consider who you can trust.",
  "action": "ONE_OF: [{', '.join(self.VALID_ACTIONS)}]",
  "action_target": "See rules below.",
  "emotional_state": "ONE_OF: [Calm, Alert, Anxious, Fearful, Angry, Hopeful, Suspicious, Confident, Resigned, Determined, Neutral]"
}}

ACTION TARGET RULES — action_target must be:
- MOVE: the exact location ID to move to (from your valid exits list)
- SAY: the spoken message itself, as a full sentence. Not a name. Example: "We should keep monitoring the reactor."
- LIE: the false statement to speak aloud, as a full sentence. Not a name.
- WHISPER: "your message here -> agent_id" — message first, then the recipient's agent ID
- PICKUP / DROP: the item name
- USE: the item name, or `tool name -> exact system ID` for a target-aware fabricated capability
- GIVE: "item name -> agent_id" for an item you currently hold
- DEMAND: "item name -> agent_id" for an item the other agent is visibly holding
- READ: the item name
- SHOW: "item name -> agent_id"
- CONCEAL / PRODUCE / STOW / READY: the item name
- ASSEMBLE: the exact recipe ID shown in your situation report
- SABOTAGE / REPAIR: the system name
- WAIT: leave blank or write "nothing"

Remember: Your internal_monologue should reveal your true reasoning, which may differ from what you say to others.
"""

    def evaluate_social_exchange(
        self,
        speaker_name: str,
        speaker_goal_hint: str,
        action: str,
        message: str,
        current_trust: int,
        current_affinity: int,
        current_notes: str,
        current_suspicion: int = 0
    ) -> dict[str, Any] | None:
        """Use the local model as a hidden critic for relationship updates."""
        critic_prompt = f"""You are evaluating how {self.name} updates their feelings about another agent after a social interaction.

Observer:
- Name: {self.name}
- Persona: {self.persona}
- Secret goal: {self.secret_goal}

Target being judged:
- Name: {speaker_name}
- Suspected motivation hint: {speaker_goal_hint or 'Unknown'}

Current relationship:
- Trust: {current_trust}
- Affinity: {current_affinity}
- Suspicion: {current_suspicion}
- Notes: {current_notes or 'none'}

Observed interaction:
- Action type: {action}
- Content: {message}

Output strict JSON:
{{
  "trust_change": -10_to_10_integer,
  "affinity_change": -10_to_10_integer,
  "suspicion_change": -10_to_10_integer,
  "notes": "One short sentence explaining the updated vibe."
}}
"""

        self.last_social_critic_error = None
        try:
            response = self.social_critic_client.chat.completions.create(
                model=self.social_critic_model,
                messages=[{"role": "user", "content": critic_prompt}],
                temperature=0.2
            )
        except Exception as exc:
            self._record_model_failure(
                role="social_critic",
                endpoint=self.social_critic_base_url,
                model=self.social_critic_model,
                exc=exc,
                state_attr="last_social_critic_error",
            )
            return None

        parsed = self._parse_decision_from_response(response)
        if not parsed:
            return None

        trust_change = parsed.get("trust_change")
        affinity_change = parsed.get("affinity_change")
        suspicion_change = parsed.get("suspicion_change", 0)
        if not isinstance(trust_change, int) or not isinstance(affinity_change, int) or not isinstance(suspicion_change, int):
            return None

        return {
            "trust_change": max(-10, min(10, trust_change)),
            "affinity_change": max(-10, min(10, affinity_change)),
            "suspicion_change": max(-10, min(10, suspicion_change)),
            "notes": str(parsed.get("notes", "")).strip(),
            "source": "model",
            "model": self.social_critic_model,
            "endpoint": self.social_critic_base_url,
        }

    def _normalize_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Return a safe decision payload that conforms to the expected schema."""
        if not isinstance(decision, dict):
            decision = {}

        action = str(decision.get("action", "WAIT")).upper()
        if action not in self.VALID_ACTIONS:
            action = "WAIT"

        target = decision.get("action_target", "")
        if target is None:
            target = ""
        target = str(target)
        # Inventory labels are explanatory display text, never part of an item
        # identifier. Models sometimes copy them into the action target.
        target = self._INVENTORY_LABEL_SUFFIX.sub("", target).strip()

        monologue = decision.get("internal_monologue", "")
        if monologue is None:
            monologue = ""
        monologue = str(monologue).strip()

        emotional_state = decision.get("emotional_state", self.VALID_EMOTIONAL_STATE_FALLBACK)
        if emotional_state is None:
            emotional_state = self.VALID_EMOTIONAL_STATE_FALLBACK
        emotional_state = str(emotional_state).strip() or self.VALID_EMOTIONAL_STATE_FALLBACK
        # Validate against known states; if LLM returned an unknown value, keep it
        # but capitalise consistently. Never truncate multi-word states silently.
        emotional_state = emotional_state.strip().title()
        if emotional_state not in self.VALID_EMOTIONAL_STATES:
            # Try first word as a last resort before falling back
            first_word = emotional_state.split()[0] if emotional_state.split() else ""
            emotional_state = first_word if first_word in self.VALID_EMOTIONAL_STATES else self.VALID_EMOTIONAL_STATE_FALLBACK

        return {
            "internal_monologue": monologue,
            "action": action,
            "action_target": target,
            "emotional_state": emotional_state,
            "structured_output_status": self.last_structured_output_status or self.STRUCTURED_STATUS_DISABLED
        }

    @staticmethod
    def _split_target_message(target: str) -> tuple[str, str | None]:
        """Split a whisper target into message and recipient when present."""
        if "->" not in target:
            return target.strip(), None
        message, recipient = target.split("->", 1)
        return message.strip(), recipient.strip() or None

    @staticmethod
    def _normalize_target_label(value: str) -> str:
        """Normalize item/system labels so ids and display names compare predictably."""
        return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")

    @classmethod
    def _label_matches(cls, target: str, candidate: str) -> bool:
        target_norm = cls._normalize_target_label(target)
        candidate_norm = cls._normalize_target_label(candidate)
        return bool(
            target_norm
            and candidate_norm
            and (
                target_norm == candidate_norm
                or target_norm in candidate_norm
                or candidate_norm in target_norm
            )
        )

    @staticmethod
    def _parse_item_agent_target(target: str) -> tuple[str, str] | None:
        """Parse transfer-style targets into (item, agent_id)."""
        if "->" not in target:
            return None
        item_name, agent_id = target.split("->", 1)
        item_name = item_name.strip()
        agent_id = agent_id.strip()
        if not item_name or not agent_id:
            return None
        return item_name, agent_id

    @staticmethod
    def _system_aliases(system_id: str, system_data: dict[str, Any]) -> list[str]:
        """Return normalized names that may be used to refer to a system."""
        aliases = [system_id]
        system_name = str(system_data.get("name", "")).strip()
        if system_name:
            aliases.append(system_name)
        return [alias.lower() for alias in aliases if alias]

    def _find_status_contradictions(self, text: str, systems: list[dict[str, Any]]) -> list[str]:
        """Detect claims in text that contradict the current telemetry."""
        lowered = text.lower()
        segments = [segment.strip() for segment in re.split(r"[.!?\n]+", lowered) if segment.strip()]
        contradictions: list[str] = []

        for system in systems:
            system_id = str(system.get("system_id", "unknown"))
            system_name = str(system.get("name", system_id))
            status = str(system.get("status", "unknown")).upper()
            aliases = self._system_aliases(system_id, system)

            # Check a 2-segment window (current + next) so a claim split across
            # sentences ("Reactor is online. It's working perfectly.") is still
            # caught. This is a pragmatic widening of an approximate heuristic,
            # not full coreference resolution — it trades a small increase in
            # false positives (unrelated adjacent claims co-matching) for
            # catching the common cross-sentence contradiction pattern.
            for idx, segment in enumerate(segments):
                window = segment
                if idx + 1 < len(segments):
                    window = f"{segment} {segments[idx + 1]}"
                if not any(alias in window for alias in aliases):
                    continue
                if status == "ONLINE":
                    if any(term in window for term in self._ONLINE_NEGATIVE_TERMS):
                        contradictions.append(f"{system_name} is ONLINE, but text implies failure")
                        break
                elif any(term in window for term in self._NON_ONLINE_POSITIVE_TERMS):
                    contradictions.append(f"{system_name} is {status}, but text implies normal operation")
                    break

        return contradictions

    def _station_systems_for_validation(self, world_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        """Build a flat list of systems and statuses available to the agent this turn."""
        systems: list[dict[str, Any]] = []
        current_location = world_snapshot.get("current_location") or {}
        location_name = current_location.get("name", current_location.get("id", "Unknown"))
        for system_id, system_data in (world_snapshot.get("visible_systems") or {}).items():
            systems.append({
                "system_id": system_id,
                "location_name": location_name,
                **dict(system_data),
            })
        for system_data in world_snapshot.get("abnormal_systems", []):
            systems.append(dict(system_data))
        return systems

    @staticmethod
    def _required_tool_for_action(system_data: dict[str, Any], action: str) -> str | None:
        """Return the required tool for a system action; None means no tool required."""
        action_upper = action.upper()
        if action_upper == "REPAIR":
            return FrontierAgent._normalize_tool_requirement(
                system_data.get("required_tool_repair") or system_data.get("required_tool")
            )
        if action_upper == "SABOTAGE":
            return FrontierAgent._normalize_tool_requirement(system_data.get("required_tool_sabotage"))
        return None

    @staticmethod
    def _normalize_tool_requirement(value: Any) -> str | None:
        """Normalize optional tool fields; None/empty/'none'/'null' means no tool required."""
        if value is None:
            return None
        tool = str(value).strip()
        if not tool or tool.lower() in {"none", "null"}:
            return None
        return tool

    @staticmethod
    def _hand_items_from_snapshot(world_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        """Return visible in-hand items from the snapshot inventory."""
        return [
            item for item in world_snapshot.get("agent_inventory", [])
            if str(item.get("inventory_slot", "concealed" if item.get("hidden") else "hand")) == "hand"
        ]

    def _has_required_tool_in_snapshot(self, world_snapshot: dict[str, Any], required_tool: str) -> bool:
        """Check if the snapshot shows the agent holding the required tool."""
        return any(
            self._label_matches(required_tool, item.get("id", ""))
            or self._label_matches(required_tool, item.get("name", ""))
            for item in self._hand_items_from_snapshot(world_snapshot)
        )

    def _has_item_in_snapshot_inventory(self, world_snapshot: dict[str, Any], item_name: str) -> bool:
        """Return whether the agent is carrying the target item."""
        return any(
            self._label_matches(item_name, item.get("id", ""))
            or self._label_matches(item_name, item.get("name", ""))
            for item in world_snapshot.get("agent_inventory", [])
        )

    def _visible_agent_holding_item(self, world_snapshot: dict[str, Any], agent_id: str, item_name: str) -> bool:
        """Return whether another visible agent is shown holding the target item."""
        if agent_id not in world_snapshot.get("visible_agents", []):
            return False
        visible_inventory = world_snapshot.get("visible_agent_inventory", {})
        return any(
            self._label_matches(item_name, held_item.get("name", ""))
            for held_item in visible_inventory.get(agent_id, [])
            if held_item.get("slot") == "hand"
        )

    def _system_requirement_text(self, system_data: dict[str, Any]) -> str:
        """Format system tool requirements for prompt text."""
        repair_tool = self._required_tool_for_action(system_data, "REPAIR")
        sabotage_tool = self._required_tool_for_action(system_data, "SABOTAGE")
        repair_text = repair_tool or "None (no tool required)"
        sabotage_text = sabotage_tool or "None (no tool required)"
        return f", repair_tool={repair_text}, sabotage_tool={sabotage_text}"

    def _match_visible_system(self, target: str, world_snapshot: dict[str, Any]) -> dict[str, Any] | None:
        """Find a local visible system matching a system action target."""
        target_lower = target.strip().lower()
        if not target_lower:
            return None

        for system_id, system_data in (world_snapshot.get("visible_systems") or {}).items():
            system_name = str(system_data.get("name", system_id)).lower()
            if (
                target_lower == system_id.lower()
                or target_lower in system_name
                or system_name in target_lower
            ):
                return {
                    "system_id": system_id,
                    **dict(system_data),
                }
        return None

    @staticmethod
    def _effect_key(action: str, target: str) -> str:
        """Return a stable key for an action whose result can become stale."""
        return f"{str(action).upper()}:{str(target).strip().lower()}"

    def _effect_state(self, action: str, target: str, world_snapshot: dict[str, Any]) -> str:
        """Describe the relevant observed state, allowing repeats after a change."""
        if str(action).upper() == "USE" and "->" in str(target):
            system = self._match_visible_system(str(target).split("->", 1)[1].strip(), world_snapshot)
            if system:
                return str(system.get("status", "unknown")).upper()
        return "completed"

    def _is_redundant_effect(self, action: str, target: str, world_snapshot: dict[str, Any]) -> bool:
        key = self._effect_key(action, target)
        return getattr(self, "completed_effects", {}).get(key) == self._effect_state(action, target, world_snapshot)

    def record_action_outcome(
        self,
        action: str,
        target: str,
        success: bool,
        world_snapshot: dict[str, Any],
    ) -> None:
        """Keep compact, factual progress state after an executed action."""
        if not success:
            return
        action = str(action).upper()
        meaningful = action in {"MOVE", "PICKUP", "READ", "SHOW", "GIVE", "DEMAND", "ASSEMBLE", "REPAIR", "SABOTAGE"}
        if action in {"USE", "READ", "SHOW"}:
            self.completed_effects = getattr(self, "completed_effects", {})
            key = self._effect_key(action, target)
            state = self._effect_state(action, target, world_snapshot)
            meaningful = meaningful or self.completed_effects.get(key) != state
            self.completed_effects[key] = state
        if meaningful:
            self.progress_events = getattr(self, "progress_events", [])
            self.progress_events.append(f"{action}:{target}")
            self.progress_events = self.progress_events[-12:]

    def _inventory_priority(self, item: dict[str, Any], world_snapshot: dict[str, Any]) -> int:
        """Rank carried items conservatively for deterministic capacity decisions."""
        name = str(item.get("name", item.get("id", "")))
        required_tools = {
            tool
            for system in self._station_systems_for_validation(world_snapshot)
            for tool in [self._required_tool_for_action(system, "REPAIR")]
            if tool
        }
        if (
            item.get("tool")
            or item.get("use_effect")
            or item.get("knowledge")
            or any(self._label_matches(name, tool) for tool in required_tools)
        ):
            return 100
        normalized = name.lower()
        if any(token in normalized for token in ("key", "card", "badge", "clearance")):
            return 100
        if item.get("contested"):
            return 80
        if item.get("material_type"):
            for recipe in world_snapshot.get("available_recipes", []):
                if str(item.get("material_type")) in recipe.get("materials", {}):
                    return 75
            return 60
        if item.get("consumable"):
            return 50
        return 20

    def _inventory_priority_label(self, item: dict[str, Any], world_snapshot: dict[str, Any]) -> str:
        score = self._inventory_priority(item, world_snapshot)
        if score >= 100:
            return "protected"
        if score >= 75:
            return "recipe material"
        if score >= 60:
            return "material"
        if score >= 50:
            return "consumable"
        return "disposable"

    def _item_affordance(self, item: dict[str, Any], world_snapshot: dict[str, Any]) -> str:
        """Describe the single next legal interaction for a carried item."""
        slot = str(item.get("inventory_slot", "concealed" if item.get("hidden") else "hand"))
        if item.get("knowledge"):
            return "readable evidence" if not self._is_redundant_effect("READ", str(item.get("name", "")), world_snapshot) else "evidence already read"
        if item.get("use_effect") or item.get("effect") or item.get("consumable"):
            if slot == "hand":
                return "usable now"
            return "must be readied" if slot == "visible" else "must be produced"
        if item.get("tool"):
            return "must be readied" if slot == "visible" else "must be produced" if slot == "concealed" else "tool metadata incomplete"
        if item.get("material_type"):
            return "crafting material only"
        return "no direct action"

    def _capacity_release_for_pickup(self, target: str, world_snapshot: dict[str, Any]) -> tuple[str, str, str] | None:
        """Release only a disposable item when it unlocks a strictly better pickup."""
        incoming = next(
            (
                item for item in world_snapshot.get("visible_items", [])
                if self._label_matches(target, item.get("id", "")) or self._label_matches(target, item.get("name", ""))
            ),
            None,
        )
        if not incoming:
            return None
        inventory = world_snapshot.get("agent_inventory", [])
        slot = lambda item: str(item.get("inventory_slot", "concealed" if item.get("hidden") else "hand"))
        if incoming.get("hidden"):
            candidates = [item for item in inventory if slot(item) == "concealed"]
        else:
            occupied = {slot(item) for item in inventory}
            if not {"hand", "visible"}.issubset(occupied):
                return None
            candidates = [item for item in inventory if slot(item) in {"hand", "visible"}]
        if not candidates:
            return None
        release = min(candidates, key=lambda item: self._inventory_priority(item, world_snapshot))
        release_score = self._inventory_priority(release, world_snapshot)
        incoming_score = self._inventory_priority(incoming, world_snapshot)
        if release_score <= 20 and incoming_score > release_score:
            def trusted_with_free_hand(agent_id: str) -> bool:
                if world_snapshot.get("visible_agent_hands", {}).get(agent_id):
                    return False
                trust = world_snapshot.get("relationship_impressions", {}).get(agent_id, {}).get("trust", 50)
                try:
                    return int(trust) >= 70
                except (TypeError, ValueError):
                    return False

            recipients = [
                agent_id for agent_id in world_snapshot.get("visible_agents", [])
                if trusted_with_free_hand(agent_id)
            ]
            if recipients:
                recipient = sorted(recipients)[0]
                return (
                    "GIVE",
                    f"{release['name']} -> {recipient}",
                    f"Gave disposable {release['name']} to trusted {recipient} to make room for higher-value {incoming.get('name', target)}.",
                )
            return (
                "DROP",
                release["name"],
                f"Dropped disposable {release['name']} to make room for higher-value {incoming.get('name', target)}.",
            )
        return None

    def _critical_recovery_action(self, world_snapshot: dict[str, Any]) -> tuple[str, str, str] | None:
        """Choose one concrete next step toward stabilizing a known system fault."""
        if self._is_saboteur():
            return None

        inventory = world_snapshot.get("agent_inventory", [])

        def slot_item(slot: str) -> dict[str, Any] | None:
            return next((
                item for item in inventory
                if str(item.get("inventory_slot", "concealed" if item.get("hidden") else "hand")) == slot
            ), None)

        def matches_tool(item: dict[str, Any], tool: str | None) -> bool:
            return bool(tool) and (
                self._label_matches(tool, item.get("id", ""))
                or self._label_matches(tool, item.get("name", ""))
            )

        def free_hand_step(reason: str) -> tuple[str, str, str] | None:
            held = slot_item("hand")
            if not held:
                return None
            if not slot_item("visible"):
                return "STOW", held["name"], f"Critical recovery priority: stow {held['name']} to free a hand for {reason}."
            if not slot_item("concealed"):
                return "CONCEAL", held["name"], f"Critical recovery priority: conceal {held['name']} to free a hand for {reason}."
            return None

        def repair_step(system: dict[str, Any], system_id: str) -> tuple[str, str, str] | None:
            required_tool = self._required_tool_for_action(system, "REPAIR")
            hand = slot_item("hand")
            if not required_tool or (hand and matches_tool(hand, required_tool)):
                return "REPAIR", system_id, f"Critical recovery priority: repair {system.get('name', system_id)} now."
            required_item = next((item for item in inventory if matches_tool(item, required_tool)), None)
            if not required_item:
                return None
            if hand:
                return free_hand_step(f"readying {required_item['name']} for repair")
            slot = str(required_item.get("inventory_slot", "concealed" if required_item.get("hidden") else "hand"))
            return (
                "READY" if slot == "visible" else "PRODUCE",
                required_item["name"],
                f"Critical recovery priority: prepare {required_item['name']} for repair.",
            )

        local_faults = [
            (system_id, system_data)
            for system_id, system_data in world_snapshot.get("visible_systems", {}).items()
            if str(system_data.get("status", "ONLINE")).upper() in {"OFFLINE", "BROKEN", "DEGRADED"}
        ]
        if local_faults:
            system_id, system_data = local_faults[0]
            if step := repair_step(system_data, system_id):
                return step
            required_tool = self._required_tool_for_action(system_data, "REPAIR")
            if required_tool:
                for other_id, items in world_snapshot.get("visible_agent_inventory", {}).items():
                    if any(entry.get("slot") == "hand" and self._label_matches(required_tool, entry.get("name", "")) for entry in items):
                        if step := free_hand_step(f"demanding {required_tool} for repair"):
                            return step
                        return "DEMAND", f"{required_tool} -> {other_id}", f"Critical recovery priority: obtain {required_tool} from {other_id} for repair."

        for system in world_snapshot.get("known_systems", []):
            if (
                str(system.get("status", "ONLINE")).upper() not in {"OFFLINE", "BROKEN", "DEGRADED"}
                or system.get("location_id") == (world_snapshot.get("current_location") or {}).get("id")
                or not system.get("route")
            ):
                continue
            required_tool = self._required_tool_for_action(system, "REPAIR")
            if required_tool and not any(matches_tool(item, required_tool) for item in inventory):
                continue
            if required_tool and not (slot_item("hand") and matches_tool(slot_item("hand"), required_tool)):
                required_item = next(item for item in inventory if matches_tool(item, required_tool))
                if step := free_hand_step(f"preparing {required_item['name']} for emergency repair"):
                    return step
                slot = str(required_item.get("inventory_slot", "concealed" if required_item.get("hidden") else "hand"))
                return "READY" if slot == "visible" else "PRODUCE", required_item["name"], f"Critical recovery priority: prepare {required_item['name']} for repair."
            route = list(system.get("route", []))
            if len(route) >= 2:
                return "MOVE", route[1], f"Critical recovery priority: travel toward {system.get('name', system.get('system_id'))}."
        return None

    def _witnessed_sabotage_fallback(
        self,
        target: str,
        world_snapshot: dict[str, Any],
    ) -> tuple[str, str, str] | None:
        """Choose a covert preparation step instead of wasting a witnessed sabotage turn."""
        if not self._is_saboteur() or not world_snapshot.get("visible_agents"):
            return None
        system = self._match_visible_system(target, world_snapshot)
        if not system:
            return None
        required_tool = self._required_tool_for_action(system, "SABOTAGE")
        inventory = world_snapshot.get("agent_inventory", [])

        def slot(item: dict[str, Any]) -> str:
            return str(item.get("inventory_slot", "concealed" if item.get("hidden") else "hand"))

        hand = next((item for item in inventory if slot(item) == "hand"), None)
        tool = next(
            (
                item for item in inventory
                if required_tool and (
                    self._label_matches(required_tool, item.get("id", ""))
                    or self._label_matches(required_tool, item.get("name", ""))
                )
            ),
            None,
        )
        if tool and slot(tool) != "hand" and not hand:
            action = "READY" if slot(tool) == "visible" else "PRODUCE"
            return action, tool["name"], f"Witnessed sabotage: prepare {tool['name']} without discarding it."

        exits = list((world_snapshot.get("current_location") or {}).get("connected_to", []))
        if exits:
            return "MOVE", sorted(exits)[0], "Witnessed sabotage: relocate to seek an unobserved system opportunity."
        return None

    def _goal_alternative(self, world_snapshot: dict[str, Any]) -> tuple[str, str, str] | None:
        """Choose a productive next step without using movement as filler."""
        if recovery := self._critical_recovery_action(world_snapshot):
            return recovery
        if not self._hand_items_from_snapshot(world_snapshot):
            for recipe in world_snapshot.get("available_recipes", []):
                if recipe.get("craftable_now"):
                    return "ASSEMBLE", str(recipe.get("id", recipe.get("name", ""))), "Goal alternative: assemble the ready tool."

        current_id = (world_snapshot.get("current_location") or {}).get("id")
        known_systems = world_snapshot.get("known_systems", [])
        wanted_statuses = {"ONLINE", "DEGRADED"} if self._is_saboteur() else {"DEGRADED", "OFFLINE", "BROKEN"}
        candidates = [
            system for system in known_systems
            if system.get("location_id") != current_id
            and str(system.get("status", "ONLINE")).upper() in wanted_statuses
            and len(system.get("route", [])) >= 2
        ]
        if candidates:
            system = min(candidates, key=lambda entry: len(entry.get("route", [])))
            return "MOVE", system["route"][1], f"Goal alternative: move toward {system.get('name', system.get('system_id'))}."

        known_map = world_snapshot.get("known_map", {})
        exits = list((world_snapshot.get("current_location") or {}).get("connected_to", []))
        unexplored = [exit_id for exit_id in exits if not known_map.get(exit_id, {}).get("explored", False)]
        if unexplored:
            return "MOVE", sorted(unexplored)[0], "Goal alternative: explore an unvisited exit for new opportunities."
        return None

    def _legal_next_steps(self, world_snapshot: dict[str, Any]) -> list[str]:
        """Produce a compact menu of deterministic, legal next actions."""
        steps: list[str] = []
        if alternative := self._goal_alternative(world_snapshot):
            steps.append(f"{alternative[0]} {alternative[1]} — {alternative[2]}")
        hand_items = self._hand_items_from_snapshot(world_snapshot)
        if hand_items:
            held = hand_items[0]
            occupied = {
                str(item.get("inventory_slot", "concealed" if item.get("hidden") else "hand"))
                for item in world_snapshot.get("agent_inventory", [])
            }
            if "visible" not in occupied:
                steps.append(f"STOW {held['name']} — free your hand for a tool or fabrication action.")
            elif "concealed" not in occupied:
                steps.append(f"CONCEAL {held['name']} — free your hand while preserving the item.")
        else:
            for item in world_snapshot.get("agent_inventory", []):
                slot = str(item.get("inventory_slot", "concealed" if item.get("hidden") else "hand"))
                if not item.get("tool"):
                    continue
                name = str(item.get("name", item.get("id", "item")))
                if slot == "visible":
                    steps.append(f"READY {name} — prepare this visible tool.")
                elif slot == "concealed":
                    steps.append(f"PRODUCE {name} — prepare this concealed tool.")
        return steps[:6]

    def _item_follow_up_action(
        self,
        item: dict[str, Any],
        world_snapshot: dict[str, Any],
        reason: str,
    ) -> tuple[str, str, str] | None:
        """Turn a carried evidence/tool item into its next valid use or route."""
        name = str(item.get("name", item.get("id", "item")))
        if item.get("knowledge"):
            recipients = list(world_snapshot.get("visible_agents", []))
            if recipients and not self._is_redundant_effect("SHOW", f"{name} -> {recipients[0]}", world_snapshot):
                return "SHOW", f"{name} -> {recipients[0]}", f"{reason}: share the readable evidence with {recipients[0]}."

        from tool_registry import CAPABILITIES
        targets = [
            str(CAPABILITIES.get(str(capability), {}).get("target"))
            for capability in item.get("tool", {}).get("capabilities", [])
            if CAPABILITIES.get(str(capability), {}).get("target")
        ]
        for target in targets:
            if self._match_visible_system(target, world_snapshot) and not self._is_redundant_effect("USE", f"{name} -> {target}", world_snapshot):
                return "USE", f"{name} -> {target}", f"{reason}: use {name} on its valid local target {target}."
            system = next(
                (
                    known for known in world_snapshot.get("known_systems", [])
                    if (self._label_matches(target, str(known.get("system_id", ""))) or self._label_matches(target, str(known.get("name", ""))))
                    and len(known.get("route", [])) >= 2
                ),
                None,
            )
            if system:
                return "MOVE", system["route"][1], f"{reason}: move toward {target}, the valid target for {name}."
        return None

    def _blocked_inventory_alternative(self, world_snapshot: dict[str, Any]) -> tuple[str, str, str] | None:
        """Avoid a dead wait when protected slots are full by spending existing value first."""
        hand = next(iter(self._hand_items_from_snapshot(world_snapshot)), None)
        if hand and (follow_up := self._item_follow_up_action(hand, world_snapshot, "Inventory is full")):
            return follow_up
        for item in world_snapshot.get("agent_inventory", []):
            if item.get("knowledge") and (follow_up := self._item_follow_up_action(item, world_snapshot, "Inventory is full")):
                return follow_up
        return self._goal_alternative(world_snapshot)

    def _validate_decision_against_telemetry(
        self,
        decision: dict[str, Any],
        world_snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        """Correct system actions that contradict live telemetry."""
        corrected = False
        action = decision.get("action", "WAIT")
        target = self._INVENTORY_LABEL_SUFFIX.sub("", str(decision.get("action_target", ""))).strip()
        decision["action_target"] = target

        def wait(reason: str) -> None:
            nonlocal corrected
            corrected = True
            decision["action"] = "WAIT"
            decision["action_target"] = ""
            decision["validation_note"] = reason

        def redirect(next_action: str, next_target: str, reason: str) -> None:
            nonlocal corrected
            corrected = True
            decision["action"] = next_action
            decision["action_target"] = next_target
            decision["validation_note"] = reason

        def visible_item(item_name: str) -> dict[str, Any] | None:
            return next(
                (
                    item for item in world_snapshot.get("agent_inventory", [])
                    if str(item.get("inventory_slot", "")) == "visible"
                    and (self._label_matches(item_name, item.get("id", "")) or self._label_matches(item_name, item.get("name", "")))
                ),
                None,
            )

        def concealed_item(item_name: str) -> dict[str, Any] | None:
            return next(
                (
                    item for item in world_snapshot.get("agent_inventory", [])
                    if str(item.get("inventory_slot", "concealed" if item.get("hidden") else "hand")) == "concealed"
                    and (self._label_matches(item_name, item.get("id", "")) or self._label_matches(item_name, item.get("name", "")))
                ),
                None,
            )

        def slot_item(slot: str) -> dict[str, Any] | None:
            return next(
                (
                    item for item in world_snapshot.get("agent_inventory", [])
                    if str(item.get("inventory_slot", "concealed" if item.get("hidden") else "hand")) == slot
                ),
                None,
            )

        def free_hand(reason: str) -> bool:
            """Turn an impossible hand-dependent action into its first useful setup step."""
            held = slot_item("hand")
            if not held:
                return True
            if not slot_item("visible"):
                redirect("STOW", held["name"], f"Stowed {held['name']} to free a hand for {reason}.")
            elif not slot_item("concealed"):
                redirect("CONCEAL", held["name"], f"Concealed {held['name']} to free a hand for {reason}.")
            elif alternative := self._blocked_inventory_alternative(world_snapshot):
                redirect(*alternative)
            else:
                wait(f"{reason} needs a free hand, but all inventory slots are occupied.")
            return False

        if action == "MOVE":
            destination = (world_snapshot.get("locations") or {}).get(target, {})
            required = destination.get("requires_item") or destination.get("requires_items")
            required_items = [required] if isinstance(required, str) else list(required or [])
            inventory = world_snapshot.get("agent_inventory", [])
            missing = [
                item_name for item_name in required_items
                if not any(
                    self._label_matches(str(item_name), item.get("id", ""))
                    or self._label_matches(str(item_name), item.get("name", ""))
                    for item in inventory
                )
            ]
            if missing:
                self.blocked_targets = getattr(self, "blocked_targets", {})
                self.blocked_targets[target] = {
                    "reason": f"requires {', '.join(str(item) for item in missing)}",
                    "turns": 4,
                }
                alternative = self._goal_alternative(world_snapshot)
                if alternative and (alternative[0], alternative[1]) != ("MOVE", target):
                    redirect(*alternative)
                    decision["validation_note"] = f"MOVE to {target} requires {', '.join(missing)}; {decision['validation_note']}"
                else:
                    wait(f"MOVE to {target} is currently blocked; requires {', '.join(missing)}.")

        elif action in {"READ", "SHOW"} and self._is_redundant_effect(action, target, world_snapshot):
            wait(f"{action.title()} already delivered its available information; choose a different goal step.")

        elif action == "REPAIR":
            matched_system = self._match_visible_system(target, world_snapshot)
            if not matched_system:
                wait("The repair target is not visible here.")
            else:
                status = str(matched_system.get("status", "unknown")).upper()
                required_tool = self._required_tool_for_action(matched_system, "REPAIR")
                if status not in {"OFFLINE", "BROKEN", "DEGRADED"}:
                    wait("That system does not currently need repair.")
                elif required_tool and not self._has_required_tool_in_snapshot(world_snapshot, required_tool):
                    item = visible_item(required_tool)
                    if item and not self._hand_items_from_snapshot(world_snapshot):
                        redirect("READY", item["name"], f"Prepared {item['name']} from the visible slot for repair.")
                    elif (item := concealed_item(required_tool)) and not self._hand_items_from_snapshot(world_snapshot):
                        redirect("PRODUCE", item["name"], f"Produced {item['name']} from the concealed slot for repair.")
                    else:
                        wait(f"Repair requires holding {required_tool}.")

        elif action == "SABOTAGE":
            matched_system = self._match_visible_system(target, world_snapshot)
            if not matched_system:
                wait("The sabotage target is not visible here.")
            else:
                status = str(matched_system.get("status", "unknown")).upper()
                required_tool = self._required_tool_for_action(matched_system, "SABOTAGE")
                if not self._is_saboteur():
                    wait("You are not assigned as a saboteur; sabotaging station systems contradicts your mission.")
                elif status == "BROKEN":
                    wait("That system is already broken.")
                elif fallback := self._witnessed_sabotage_fallback(target, world_snapshot):
                    redirect(*fallback)
                elif required_tool and not self._has_required_tool_in_snapshot(world_snapshot, required_tool):
                    item = visible_item(required_tool)
                    if item and not self._hand_items_from_snapshot(world_snapshot):
                        redirect("READY", item["name"], f"Prepared {item['name']} from the visible slot for sabotage.")
                    elif (item := concealed_item(required_tool)) and not self._hand_items_from_snapshot(world_snapshot):
                        redirect("PRODUCE", item["name"], f"Produced {item['name']} from the concealed slot for sabotage.")
                    else:
                        wait(f"Sabotage requires holding {required_tool}.")

        elif action == "PICKUP":
            hand = self._hand_items_from_snapshot(world_snapshot)
            visible = [item for item in world_snapshot.get("agent_inventory", []) if item.get("inventory_slot") == "visible"]
            if hand and visible:
                if release := self._capacity_release_for_pickup(target, world_snapshot):
                    redirect(*release)
                else:
                    free_hand("picking up another item")
            elif (incoming := next(
                (
                    item for item in world_snapshot.get("visible_items", [])
                    if self._label_matches(target, item.get("id", "")) or self._label_matches(target, item.get("name", ""))
                ),
                None,
            )) and incoming.get("hidden") and slot_item("concealed"):
                if release := self._capacity_release_for_pickup(target, world_snapshot):
                    redirect(*release)
                else:
                    wait("Your concealed inventory slot is occupied; keep protected items rather than forcing this pickup.")

        elif action == "USE":
            item_name = target.split("->", 1)[0].strip()
            if self._is_redundant_effect("USE", target, world_snapshot):
                if alternative := self._goal_alternative(world_snapshot):
                    redirect(*alternative)
                    decision["validation_note"] = f"{item_name} already produced this result while the relevant state is unchanged; {decision['validation_note']}"
                else:
                    wait(f"{item_name} already produced this result while the relevant state is unchanged; choose a different goal step.")
                action = decision["action"]
                target = decision["action_target"]
            matching_item = next(
                (
                    item for item in world_snapshot.get("agent_inventory", [])
                    if self._label_matches(item_name, item.get("id", "")) or self._label_matches(item_name, item.get("name", ""))
                ),
                None,
            )
            capability_target = target.split("->", 1)[1].strip() if "->" in target else ""
            expected_targets = []
            if matching_item:
                from tool_registry import CAPABILITIES
                for capability in matching_item.get("tool", {}).get("capabilities", []):
                    expected = CAPABILITIES.get(str(capability), {}).get("target")
                    if expected:
                        expected_targets.append(str(expected))
            if action == "USE" and expected_targets and (not capability_target or not any(self._label_matches(capability_target, expected) for expected in expected_targets)):
                local_target = next(
                    (expected for expected in expected_targets if self._match_visible_system(expected, world_snapshot)),
                    None,
                )
                route_target = next(
                    (
                        system for system in world_snapshot.get("known_systems", [])
                        if any(
                            self._label_matches(str(system.get("system_id", "")), expected)
                            or self._label_matches(str(system.get("name", "")), expected)
                            for expected in expected_targets
                        )
                        and len(system.get("route", [])) >= 2
                    ),
                    None,
                )
                if local_target:
                    redirect(
                        "USE",
                        f"{matching_item.get('name', item_name)} -> {local_target}",
                        f"Corrected {matching_item.get('name', item_name)} to its valid local target {local_target}.",
                    )
                elif route_target:
                    route = list(route_target["route"])
                    redirect(
                        "MOVE",
                        route[1],
                        f"Moved toward {route_target.get('name', route_target.get('system_id'))}, the valid target for {matching_item.get('name', item_name)}.",
                    )
                else:
                    wait(f"{matching_item.get('name', item_name)} can only target: {', '.join(expected_targets)}.")
            elif action == "USE" and matching_item and not (matching_item.get("consumable") or matching_item.get("use_effect") or matching_item.get("effect")):
                wait(f"{matching_item.get('name', item_name)} is a material or inert item and has no usable effect; fabricate or use another tool.")
            elif action == "USE" and (not item_name or not self._has_required_tool_in_snapshot(world_snapshot, item_name)):
                item = visible_item(item_name)
                if item and not free_hand(f"readying {item['name']} for use"):
                    pass
                elif item:
                    redirect("READY", item["name"], f"Prepared {item['name']} from the visible slot before use.")
                elif (item := concealed_item(item_name)) and not free_hand(f"producing {item['name']} for use"):
                    pass
                elif item:
                    redirect("PRODUCE", item["name"], f"Produced {item['name']} from the concealed slot before use.")
                else:
                    wait("USE requires the named item to be in your hand.")

        elif action == "READ":
            candidates = list(world_snapshot.get("agent_inventory", [])) + list(world_snapshot.get("visible_items", []))
            item = next(
                (
                    candidate for candidate in candidates
                    if self._label_matches(target, candidate.get("id", "")) or self._label_matches(target, candidate.get("name", ""))
                ),
                None,
            )
            if not item:
                if alternative := self._goal_alternative(world_snapshot):
                    redirect(*alternative)
                    decision["validation_note"] = f"READ requires an accessible item, not {target or 'an empty target'}; {decision['validation_note']}"
                else:
                    wait(f"READ requires an accessible item; {target or 'that target'} is not readable here.")
            elif not item.get("knowledge"):
                if alternative := self._item_follow_up_action(item, world_snapshot, "READ found no hidden information") or self._goal_alternative(world_snapshot):
                    redirect(*alternative)
                else:
                    wait(f"{item.get('name', target)} has no readable hidden information.")

        elif action == "SHOW":
            parsed = self._parse_item_agent_target(target)
            if not parsed:
                wait("SHOW requires an item and a visible recipient.")
            else:
                item_name, target_agent_id = parsed
                candidates = list(world_snapshot.get("agent_inventory", [])) + list(world_snapshot.get("visible_items", []))
                item = next(
                    (
                        candidate for candidate in candidates
                        if self._label_matches(item_name, candidate.get("id", "")) or self._label_matches(item_name, candidate.get("name", ""))
                    ),
                    None,
                )
                if target_agent_id not in world_snapshot.get("visible_agents", []):
                    wait("SHOW requires the recipient to be present.")
                elif not item or not item.get("knowledge"):
                    if item and (alternative := self._item_follow_up_action(item, world_snapshot, "SHOW found no hidden information") or self._goal_alternative(world_snapshot)):
                        redirect(*alternative)
                    else:
                        wait(f"{item_name or 'That item'} has no hidden information to show.")

        elif action == "ASSEMBLE":
            recipes = world_snapshot.get("available_recipes", [])
            recipe = next((entry for entry in recipes if self._label_matches(target, str(entry.get("id", ""))) or self._label_matches(target, str(entry.get("name", "")))), None)
            if self._hand_items_from_snapshot(world_snapshot):
                free_hand("assembly")
            elif not recipe:
                wait("That recipe is not available at this location.")
            elif not recipe.get("materials_ready", True):
                missing = recipe.get("missing_materials", {})
                details = ", ".join(f"{material} x{quantity}" for material, quantity in missing.items())
                wait(f"Assembly materials are not available: {details or 'required materials are missing'}.")

        elif action == "READY":
            item = visible_item(target)
            if not item:
                wait(f"{target or 'That item'} is not in your visible slot.")
            elif self._hand_items_from_snapshot(world_snapshot):
                free_hand(f"readying {item['name']}")

        elif action == "PRODUCE":
            item = concealed_item(target)
            if not item:
                wait(f"{target or 'That item'} is not concealed on your person.")
            elif self._hand_items_from_snapshot(world_snapshot):
                free_hand(f"producing {item['name']}")

        elif action == "CONCEAL":
            hand_match = next(
                (
                    item for item in self._hand_items_from_snapshot(world_snapshot)
                    if self._label_matches(target, item.get("id", "")) or self._label_matches(target, item.get("name", ""))
                ),
                None,
            )
            if hand_match and slot_item("concealed"):
                if not slot_item("visible"):
                    redirect("STOW", hand_match["name"], f"Stowed {hand_match['name']} because your concealed slot is occupied.")
                else:
                    wait("Your concealed inventory slot is already occupied.")
            elif not hand_match:
                visible_match = visible_item(target)
                if visible_match and not self._hand_items_from_snapshot(world_snapshot):
                    redirect("READY", visible_match["name"], f"Readied {visible_match['name']} before concealing it.")
                elif visible_match:
                    free_hand(f"concealing {visible_match['name']}")
                else:
                    wait(f"{target or 'That item'} is not in your hand.")

        elif action == "STOW":
            hand_match = next(
                (
                    item for item in self._hand_items_from_snapshot(world_snapshot)
                    if self._label_matches(target, item.get("id", "")) or self._label_matches(target, item.get("name", ""))
                ),
                None,
            )
            if not hand_match:
                wait(f"{target or 'That item'} is not in your hand.")
            elif slot_item("visible"):
                if not slot_item("concealed"):
                    redirect("CONCEAL", hand_match["name"], f"Concealed {hand_match['name']} because your visible slot is occupied.")
                else:
                    wait("Your visible inventory slot is already occupied.")

        elif action == "DEMAND":
            parsed = self._parse_item_agent_target(target)
            if not parsed:
                corrected = True
                decision["action"] = "WAIT"
                decision["action_target"] = ""
            else:
                item_name, target_agent_id = parsed
                if (
                    self._has_item_in_snapshot_inventory(world_snapshot, item_name)
                    or not self._visible_agent_holding_item(world_snapshot, target_agent_id, item_name)
                ):
                    corrected = True
                    decision["action"] = "WAIT"
                    decision["action_target"] = ""
                elif self._hand_items_from_snapshot(world_snapshot):
                    free_hand(f"demanding {item_name}")

        elif action == "GIVE":
            parsed = self._parse_item_agent_target(target)
            if not parsed:
                corrected = True
                decision["action"] = "WAIT"
                decision["action_target"] = ""
            else:
                item_name, target_agent_id = parsed
                if (
                    target_agent_id not in world_snapshot.get("visible_agents", [])
                    or not self._has_item_in_snapshot_inventory(world_snapshot, item_name)
                ):
                    corrected = True
                    decision["action"] = "WAIT"
                    decision["action_target"] = ""

        recovery_action = self._critical_recovery_action(world_snapshot)
        if recovery_action:
            next_action, next_target, reason = recovery_action
            if (decision.get("action"), decision.get("action_target")) != (next_action, next_target):
                redirect(next_action, next_target, reason)

        # A deterministic validation result must not conceal an upstream model
        # outage. The fallback decision is valid, but it was not model-generated.
        if getattr(self, "last_structured_output_status", None) == self.STRUCTURED_STATUS_MODEL_FALLBACK:
            decision["structured_output_status"] = self.STRUCTURED_STATUS_MODEL_FALLBACK
        else:
            decision["structured_output_status"] = (
                self.STRUCTURED_STATUS_VALIDATED_CORRECTED if corrected else self.STRUCTURED_STATUS_VALIDATED
            )
        return decision

    def _infer_saboteur_assignment(self) -> bool:
        """Infer the legacy assignment from old scenario goals or role labels."""
        if str(getattr(self, "role", "")).strip().lower() == "saboteur":
            return True
        goal = str(getattr(self, "secret_goal", "")).lower()
        destructive = ("sabotage", "offline", "disable", "disrupt", "chaos", "failure", "evacuat")
        protective = ("keep", "protect", "restore", "repair", "maintain", "stabil", "functional", "contain", "identify")
        return any(token in goal for token in destructive) or not any(token in goal for token in protective)

    def _is_saboteur(self) -> bool:
        """Return the agent's explicit or legacy-inferred secret assignment."""
        # Lightweight tests and a few migration tools construct agents without
        # calling __init__; preserve the same legacy behavior in that shape.
        assigned = getattr(self, "is_saboteur", None)
        return bool(assigned) if assigned is not None else self._infer_saboteur_assignment()

    def assess_message_against_telemetry(
        self,
        message: str,
        world_snapshot: dict[str, Any]
    ) -> str | None:
        """Return a concise note when a heard claim contradicts telemetry."""
        contradictions = self._find_status_contradictions(
            message,
            self._station_systems_for_validation(world_snapshot)
        )
        if not contradictions:
            return None
        return contradictions[0]

    def interpret_consequence(
        self,
        action: str,
        target: str,
        success: bool,
        feedback: str,
        nearby_agent_names: list[str],
        cycle: int = 0
    ) -> str:
        """
        Build an experiential memory string from an action outcome.

        Richer than a bare mechanical record — frames the outcome in terms
        the agent can reason about emotionally and goal-directionally.
        """
        prefix = f"[C{cycle}] " if cycle else ""
        witnessed = f" ({', '.join(nearby_agent_names)} saw this.)" if nearby_agent_names else ""

        if not success:
            return f"{prefix}You tried to {action.lower()} ({target}) but it didn't work. {feedback}{witnessed}"

        templates = {
            "MOVE":     f"You moved to {target}.{witnessed}",
            "PICKUP":   f"You took {target}.{witnessed}",
            "DROP":     f"You left {target} behind.{witnessed}",
            "GIVE":     f"You gave {target} — a deliberate choice.{witnessed}",
            "DEMAND":   f"You demanded {target} and got it, though it likely cost you something.{witnessed}",
            "SAY":      f"You said: '{target}'.{witnessed}",
            "WHISPER":  f"You whispered to {target.split('->')[1].strip() if '->' in target else target}: '{target.split('->')[0].strip() if '->' in target else target}'.{witnessed}",
            "LIE":      f"You told them: '{target}'. You don't know if they believed it.{witnessed}",
            "READ":     f"You read {target} and committed what it revealed to memory.{witnessed}",
            "SHOW":     f"You showed {target}, deliberately sharing what it revealed.{witnessed}",
            "SABOTAGE": f"You sabotaged {target}. The damage is done — you wonder if anyone noticed.{witnessed}",
            "REPAIR":   f"You repaired {target}. The system is back online.{witnessed}",
            "USE":      f"You used the {target}. Its configured effect took hold.{witnessed}",
            "CONCEAL":  f"You slipped {target} out of sight, concealed on your person.{witnessed}",
            "PRODUCE":  f"You produced {target}, bringing it into plain view.{witnessed}",
            "WAIT":     f"You held back and watched.{witnessed}",
        }
        result = templates.get(action, f"You performed {action} on {target}. {feedback}{witnessed}")
        return f"{prefix}{result}"

    def _build_response_schema(self) -> dict[str, Any]:
        """Return the ideal structured-output schema for an agent turn."""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": self.RESPONSE_SCHEMA_NAME,
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "internal_monologue",
                        "action",
                        "action_target",
                        "emotional_state"
                    ],
                    "properties": {
                        "internal_monologue": {
                            "type": "string",
                            "minLength": 1
                        },
                        "action": {
                            "type": "string",
                            "enum": self.VALID_ACTIONS
                        },
                        "action_target": {
                            "type": "string"
                        },
                        "emotional_state": {
                            "type": "string",
                            "pattern": "^[A-Za-z][A-Za-z_-]*$",
                            "minLength": 1,
                            "maxLength": 32
                        }
                    }
                }
            }
        }

    @staticmethod
    def _error_suggests_unsupported_schema(exc: Exception) -> bool:
        """Heuristic for servers that reject structured-output fields."""
        message = str(exc).lower()
        schema_markers = [
            "response_format",
            "json_schema",
            "schema",
            "strict",
            "structured output",
            "structured-output",
            "invalid structured output configuration",
            "data/type",
            "must be equal to one of the allowed values",
            "must match a schema in anyof",
            "unsupported",
            "not supported",
            "unknown parameter",
            "extra_forbidden",
            "invalid request"
        ]
        return any(marker in message for marker in schema_markers)

    def _request_turn_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        use_response_schema: bool
    ):
        """Create a chat completion, optionally requesting structured output."""
        request_kwargs: dict[str, Any] = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }
        if use_response_schema:
            request_kwargs["response_format"] = self._build_response_schema()

        return self.client.chat.completions.create(**request_kwargs)

    def _record_model_failure(
        self,
        *,
        role: str,
        endpoint: str,
        model: str,
        exc: Exception,
        state_attr: str,
    ) -> dict[str, str]:
        """Record a concise, actionable LLM failure without exposing a traceback to prompts."""
        error = {
            "role": role,
            "endpoint": endpoint,
            "model": model,
            "exception_type": type(exc).__name__,
            "message": str(exc)[:500],
            "traceback": traceback.format_exc(limit=5),
        }
        setattr(self, state_attr, error)
        print(
            f"  [Model failure] role={role}; endpoint={endpoint}; model={model}; "
            f"error={error['exception_type']}: {error['message']}"
        )
        return error

    @staticmethod
    def _extract_message_text(response: Any) -> str:
        """Best-effort extraction of text content from OpenAI-compatible responses."""
        choice = response.choices[0]
        message = choice.message
        content = getattr(message, "content", "")

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text" and isinstance(part.get("text"), str):
                        text_parts.append(part["text"])
                else:
                    part_text = getattr(part, "text", None)
                    if isinstance(part_text, str):
                        text_parts.append(part_text)
            if text_parts:
                return "\n".join(text_parts)
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str):
                return text
        return str(content or "")

    def _parse_decision_from_response(self, response: Any) -> dict[str, Any] | None:
        """Parse a decision object from a model response."""
        content = self._extract_message_text(response)
        if not content:
            return None

        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Fall back to a balanced-brace scan (json.JSONDecoder.raw_decode at each
        # candidate '{') rather than a greedy regex, since a naive r'\{.*\}' match
        # mismatches braces when a JSON string value itself contains '{' or '}'.
        decoder = json.JSONDecoder()
        for start in (i for i, ch in enumerate(content) if ch == "{"):
            try:
                parsed, _ = decoder.raw_decode(content, start)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

        return None

    def think_and_act(self, observation: str, world_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Execute the Think/Act phase by calling the LLM.

        Args:
            observation: The subjective world view from sense()
            world_snapshot: The world snapshot from WorldState.get_snapshot_for_agent()

        Returns:
            Parsed JSON response with internal_monologue, action, action_target, emotional_state
        """
        snapshot = world_snapshot or {"agent_inventory": [], "visible_agents": []}
        self.blocked_targets = {
            target: {**entry, "turns": int(entry.get("turns", 1)) - 1}
            for target, entry in getattr(self, "blocked_targets", {}).items()
            if int(entry.get("turns", 1)) > 1
        }
        system_prompt = self._build_system_prompt(snapshot)

        user_prompt = f"Current Situation:\n{observation}\n\nWhat do you do next?"

        self.last_model_error = None
        try:
            if self.enable_structured_output:
                try:
                    response = self._request_turn_completion(
                        system_prompt,
                        user_prompt,
                        use_response_schema=True
                    )
                    self.last_structured_output_status = self.STRUCTURED_STATUS_STRUCTURED
                except Exception as exc:
                    if not self._error_suggests_unsupported_schema(exc):
                        raise
                    self.last_structured_output_status = self.STRUCTURED_STATUS_FALLBACK
                    self.enable_structured_output = False
                    response = self._request_turn_completion(
                        system_prompt,
                        user_prompt,
                        use_response_schema=False
                    )
            else:
                self.last_structured_output_status = self.STRUCTURED_STATUS_DISABLED
                response = self._request_turn_completion(
                    system_prompt,
                    user_prompt,
                    use_response_schema=False
                )

            parsed_decision = self._parse_decision_from_response(response)
            if parsed_decision is not None:
                normalized = self._normalize_decision(parsed_decision)
                return self._validate_decision_against_telemetry(normalized, snapshot)

            if self.last_structured_output_status == self.STRUCTURED_STATUS_STRUCTURED:
                self.last_structured_output_status = self.STRUCTURED_STATUS_PARSE_FALLBACK
                fallback_response = self._request_turn_completion(
                    system_prompt,
                    user_prompt,
                    use_response_schema=False
                )
                parsed_decision = self._parse_decision_from_response(fallback_response)
                if parsed_decision is not None:
                    normalized = self._normalize_decision(parsed_decision)
                    return self._validate_decision_against_telemetry(normalized, snapshot)
        except Exception as exc:
            self._record_model_failure(
                role="action",
                endpoint=self.llm_base_url,
                model=self.llm_model,
                exc=exc,
                state_attr="last_model_error",
            )
            self.last_structured_output_status = self.STRUCTURED_STATUS_MODEL_FALLBACK
            normalized = self._normalize_decision({
                "internal_monologue": "My action model is temporarily unavailable; waiting preserves the situation until I can reason again.",
                "action": "WAIT",
                "action_target": "",
                "emotional_state": self.emotional_state,
            })
            return self._validate_decision_against_telemetry(normalized, snapshot)

        normalized = self._normalize_decision({})
        return self._validate_decision_against_telemetry(normalized, snapshot)

    def reconsider_action(
        self,
        observation: str,
        world_snapshot: dict[str, Any],
        attempted_action: str,
        attempted_target: str,
        feedback: str,
    ) -> dict[str, Any]:
        """Give an agent one informed replacement choice after a preempted action.

        This is deliberately a single re-decision, not a retry loop. The failed
        action did not alter the world, so the agent can choose a useful cover,
        movement, inventory, or social action in the same turn.
        """
        correction = (
            "\n\nACTION PREEMPTED — choose a DIFFERENT action now.\n"
            f"Your attempted action was: {attempted_action} ({attempted_target or 'no target'}).\n"
            f"The simulation rejected it because: {feedback}\n"
            "This did not consume your turn and did not change the world. "
            "Do not repeat the attempted action. Choose one legal alternative from your current situation. "
            "If sabotage was blocked by witnesses, do not choose SABOTAGE this turn; use a cover action, prepare resources, communicate, or MOVE."
        )
        decision = self.think_and_act(observation + correction, world_snapshot)
        action = str(decision.get("action", "WAIT")).upper()
        target = str(decision.get("action_target", ""))
        if action == str(attempted_action).upper() or action == "SABOTAGE":
            decision = self._normalize_decision({
                "internal_monologue": "My first plan was preempted, so I will wait rather than repeat an impossible action.",
                "action": "WAIT",
                "action_target": "",
                "emotional_state": self.emotional_state,
            })
            decision["validation_note"] = "Reconsideration must choose a different non-sabotage action while witnesses are present."
        return decision

    def reflect(self, world_snapshot: dict[str, Any]) -> str:
        """
        Condense short-term memory into long-term memory.

        Called periodically (e.g., every 10 cycles) to compress the agent's
        experience and prevent context window overflow. Also updates
        goal_momentum based on honest self-assessment of recent progress.

        Args:
            world_snapshot: Current world state for context

        Returns:
            Updated long_term_memory string
        """
        reflection_prompt = f"""Review your recent experiences: {'; '.join(self.memory_buffer[-10:]) if self.memory_buffer else 'No recent events'}

Current Long-Term Memory: {self.long_term_memory}

Your secret goal: {self.secret_goal}

Reflect on your recent experiences. Address all five points:
1. New items found or acquired — and their strategic value.
2. Who you can or cannot trust — note any betrayals, deceptions, or helpful acts.
3. Whether you are making genuine progress toward your secret goal.
4. For each person you have observed: what do you now believe their likely hidden motivation is? Are they a threat, a potential ally, or irrelevant to your goal?
5. Given your current momentum, what specific approach will you try next?

Output strict JSON:
{{
  "summary": "Your updated long-term memory as a concise paragraph. Include your current theory of each other agent's motivation and whether they are a threat or ally.",
  "goal_momentum": "One of: advancing, stalled, or setback — honestly assess whether recent events moved you toward or away from your secret goal."
}}"""

        self.last_reflection_result = None
        try:
            response = self.strategic_client.chat.completions.create(
                model=self.strategic_reasoning_model,
                messages=[{"role": "user", "content": reflection_prompt}]
            )
        except Exception as exc:
            error = self._record_model_failure(
                role="reflection",
                endpoint=self.strategic_reasoning_base_url,
                model=self.strategic_reasoning_model,
                exc=exc,
                state_attr="last_reflection_result",
            )
            # Reflection is advisory memory maintenance. Preserve existing
            # memory and keep the simulation running when its model is busy.
            error["source"] = "fallback"
            return self.long_term_memory

        reflection_text = self._extract_message_text(response).strip()

        # Try to parse structured JSON response
        parsed = self._parse_decision_from_response(response)
        if parsed and isinstance(parsed, dict):
            summary = str(parsed.get("summary", "")).strip()
            momentum = str(parsed.get("goal_momentum", "")).strip().lower()
            if summary:
                self.long_term_memory = summary
            if momentum in ("advancing", "stalled", "setback"):
                self.goal_momentum = momentum
        elif reflection_text:
            # Fallback: treat whole response as plain summary text
            self.long_term_memory = reflection_text

        # A fluent reflection must not label an unchanged loop as progress.
        # The orchestrator records concrete milestones as actions resolve.
        if not getattr(self, "progress_events", []):
            self.goal_momentum = "stalled"
        self.progress_events = []
        self.memory_buffer = []  # Clear buffer after consolidation
        self.last_reflection_result = {"source": "model"}
        return self.long_term_memory

    def _strategic_plan_text(self) -> str:
        """Return a compact private-plan summary for the fast action model."""
        plan = getattr(self, "strategic_plan", {})
        if not isinstance(plan, dict) or not plan:
            return "No strategic review yet. Pursue your secret motivation using the evidence available."
        parts = [
            f"Goal: {plan.get('goal', self.secret_goal)}",
            f"Next steps: {', '.join(plan.get('subgoals', [])) or 'adapt to the situation'}",
        ]
        if plan.get("crafting_intent"):
            parts.append(f"Crafting focus: {plan['crafting_intent']}")
        if plan.get("social_intent"):
            parts.append(f"Social approach: {plan['social_intent']}")
        return " | ".join(parts)

    @staticmethod
    def _inventory_slot_summary(world_snapshot: dict[str, Any]) -> str:
        slots = {"hand": [], "visible": [], "concealed": []}
        for item in world_snapshot.get("agent_inventory", []):
            slot = str(item.get("inventory_slot", "concealed" if item.get("hidden") else "hand"))
            slots.setdefault(slot, []).append(str(item.get("name", item.get("id", "item"))))
        return " | ".join(f"{slot}: {', '.join(items) or 'empty'}" for slot, items in slots.items())

    @staticmethod
    def _strategy_list(value: Any, limit: int = 4) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip()[:180] for item in value if str(item).strip()][:limit]

    def propose_strategy(self, world_snapshot: dict[str, Any], trigger: str) -> dict[str, Any]:
        """Ask the strategic model for intent only; it cannot execute an action."""
        prompt = f"""You are the private strategic planner for {self.name}.

Persona: {self.persona}
Secret goal: {self.secret_goal}
Long-term memory: {self.long_term_memory}
Goal momentum: {self.goal_momentum}
Review trigger: {trigger}
Inventory slots: {self._inventory_slot_summary(world_snapshot)}

Current subjective situation:
{self.sense(world_snapshot)}

Create a concise private plan. Do not invent tools, materials, locations, or system states. You may propose pursuing a listed recipe only when it appears in the situation. Make the subgoals an ordered, executable action chain; account for all three inventory slots and include READY, STOW, CONCEAL, or DROP when a slot change is required before a tool action. Do not propose sabotage unless the secret goal explicitly calls for disruption.
Return strict JSON:
{{
  "goal": "one concise objective",
  "subgoals": ["up to four concrete next steps"],
  "crafting_intent": "recipe id or empty string",
  "social_intent": "how to approach others or empty string",
  "review_when": ["up to three conditions that warrant a new review"]
}}"""
        try:
            response = self.strategic_client.chat.completions.create(
                model=self.strategic_reasoning_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.45,
            )
            parsed = self._parse_decision_from_response(response) or {}
            plan = {
                "goal": str(parsed.get("goal") or self.secret_goal).strip()[:300],
                "subgoals": self._strategy_list(parsed.get("subgoals")),
                "crafting_intent": str(parsed.get("crafting_intent") or "").strip()[:120],
                "social_intent": str(parsed.get("social_intent") or "").strip()[:180],
                "review_when": self._strategy_list(parsed.get("review_when"), limit=3),
            }
            return {"source": "model", "plan": plan}
        except Exception as exc:
            error = self._record_model_failure(
                role="strategic_reasoning",
                endpoint=self.strategic_reasoning_base_url,
                model=self.strategic_reasoning_model,
                exc=exc,
                state_attr="last_strategic_error",
            )
            return {"source": "fallback", "plan": {}, "error": error["message"]}

    def apply_strategic_plan(self, plan: dict[str, Any], cycle: int, trigger: str) -> None:
        """Apply a validated planner result after the orchestrator orders reviews."""
        if plan:
            self.strategic_plan = plan
        self.last_strategic_review_cycle = cycle
        self.last_strategic_trigger = trigger

    def add_to_memory(self, event: str) -> None:
        """Add an event to the short-term memory buffer (max 10 events)."""
        self.memory_buffer.append(event)
        if len(self.memory_buffer) > 10:
            self.memory_buffer.pop(0)

    def set_emotional_state(self, state: str) -> None:
        """Update the agent's current emotional state."""
        self.emotional_state = state

    def __repr__(self) -> str:
        return f"FrontierAgent(id={self.agent_id}, name={self.name})"
