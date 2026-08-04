"""
FrontierAgent - The Cognitive Unit of Silicon Frontier

Represents an autonomous entity that perceives its environment, reasons about
its goals, and takes actions through a local LLM inference engine.
"""

import json
import re
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

        # Emotional state tracking (for observation)
        self.emotional_state: str = "Neutral"
        self.last_structured_output_status: str | None = None

        # Goal momentum: agent's sense of whether they're making progress
        self.goal_momentum: str = "stalled"

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
        recipe_lines = [
            f"- {recipe.get('id')}: {recipe.get('name', recipe.get('id'))} "
            f"(materials: {recipe.get('materials', {})})"
            for recipe in world_snapshot.get("available_recipes", [])
        ]
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
            else:
                tactical_parts.append("You are unobserved this turn.")
        repairable = [
            f"{sid} ({sd.get('status', 'unknown')})"
            for sid, sd in visible_sys_map.items()
            if sd.get("status", "ONLINE") in {"OFFLINE", "BROKEN"}
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
        inventory_str = f"In hand: {', '.join(slots['hand']) or 'empty'} | Visible: {', '.join(slots['visible']) or 'empty'} | Concealed: {', '.join(slots['concealed']) or 'empty'}"
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

        return f"""You are {self.name}, the {self.role} aboard the "Silicon Frontier" research station.

YOUR IDENTITY
Persona: {self.persona}
Secret Motivation: {self.secret_goal}
Current Strategic Plan: {strategic_plan_text}
Condition: {condition_line}
Current Inventory: {inventory_str}
Fabricated Tool Capabilities:
{tool_capabilities}
Current Emotional State: {self.emotional_state} — let this genuinely color your reasoning, tone, and choices.

THE SIMULATION RULES
- The World is Discrete: You can only interact with things in your current location. To go elsewhere, you must use the MOVE command.
- Movement: You can only MOVE to locations listed under "Exits (valid MOVE targets)" in your situation report. Do not attempt to move anywhere else.
- Inventory: You have three slots — one item in hand, one visibly carried item, and one concealed item. Other agents can see your hand and visible slots, but never the concealed slot. You must have an empty hand to USE, REPAIR, or SABOTAGE with an item. STOW moves hand -> visible; READY moves visible -> hand.
- Persistence: Your memories are long-term. Refer to previous events to build trust or hold grudges.
- Truth Constraint: Do NOT invent items or people that are not in your "Current Situation" report.
- Telemetry Constraint: Treat the listed system statuses as the authoritative truth for this turn.
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
- Only choose REPAIR for a system whose visible status is OFFLINE or BROKEN.
- If a system is ONLINE or DEGRADED, do not attempt REPAIR. Consider another action instead.
- SABOTAGE is different from REPAIR: an ONLINE or DEGRADED system can be sabotaged if it is visible here.
- Do not choose SABOTAGE for a system whose visible status is already BROKEN.
- If a system lists `repair_tool=...`, you must be holding that tool in your hand to REPAIR it.
- If a system lists `sabotage_tool=...`, you must be holding that tool in your hand to SABOTAGE it.
- If the tool for the chosen system action is not listed, no tool is required; the action still requires a valid local target.
- Do not claim a system is failing unless that status is shown in the telemetry above.
- You may ASSEMBLE only a listed recipe at a listed fabrication facility. This consumes its materials and creates a real in-world tool; do not invent recipes or tool effects.
- For a fabricated tool with a listed capability target, use `USE tool name -> exact system ID`. Tools without a target-aware capability still use `USE tool name`.

ITEM TRANSFER RULES
- DEMAND means taking an item from another visible agent. Do not DEMAND an item you already hold.
- Only choose DEMAND for an item currently shown in that other agent's visible hand.
- GIVE means handing over an item you currently hold.

YOUR KNOWLEDGE SO FAR
Long-term memories: {self.long_term_memory}
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

        try:
            response = self.social_critic_client.chat.completions.create(
                model=self.social_critic_model,
                messages=[{"role": "user", "content": critic_prompt}],
                temperature=0.2
            )
        except Exception as exc:
            print(f"  [Warning] Social critic evaluation failed for {self.name}: {exc}")
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

    def _validate_decision_against_telemetry(
        self,
        decision: dict[str, Any],
        world_snapshot: dict[str, Any]
    ) -> dict[str, Any]:
        """Correct system actions that contradict live telemetry."""
        corrected = False
        action = decision.get("action", "WAIT")
        target = decision.get("action_target", "")

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

        if action == "REPAIR":
            matched_system = self._match_visible_system(target, world_snapshot)
            if not matched_system:
                wait("The repair target is not visible here.")
            else:
                status = str(matched_system.get("status", "unknown")).upper()
                required_tool = self._required_tool_for_action(matched_system, "REPAIR")
                if status not in {"OFFLINE", "BROKEN"}:
                    wait("That system does not currently need repair.")
                elif required_tool and not self._has_required_tool_in_snapshot(world_snapshot, required_tool):
                    item = visible_item(required_tool)
                    if item and not self._hand_items_from_snapshot(world_snapshot):
                        redirect("READY", item["name"], f"Prepared {item['name']} from the visible slot for repair.")
                    else:
                        wait(f"Repair requires holding {required_tool}.")

        elif action == "SABOTAGE":
            matched_system = self._match_visible_system(target, world_snapshot)
            if not matched_system:
                wait("The sabotage target is not visible here.")
            else:
                status = str(matched_system.get("status", "unknown")).upper()
                required_tool = self._required_tool_for_action(matched_system, "SABOTAGE")
                if not self._goal_permits_sabotage():
                    wait("Your stated goal is protective; sabotaging station systems contradicts it.")
                elif status == "BROKEN":
                    wait("That system is already broken.")
                elif required_tool and not self._has_required_tool_in_snapshot(world_snapshot, required_tool):
                    item = visible_item(required_tool)
                    if item and not self._hand_items_from_snapshot(world_snapshot):
                        redirect("READY", item["name"], f"Prepared {item['name']} from the visible slot for sabotage.")
                    else:
                        wait(f"Sabotage requires holding {required_tool}.")

        elif action == "PICKUP":
            hand = self._hand_items_from_snapshot(world_snapshot)
            visible = [item for item in world_snapshot.get("agent_inventory", []) if item.get("inventory_slot") == "visible"]
            if hand and visible:
                wait("Your hand and visible inventory slots are occupied; DROP or CONCEAL an item first.")

        elif action == "USE":
            item_name = target.split("->", 1)[0].strip()
            if not item_name or not self._has_required_tool_in_snapshot(world_snapshot, item_name):
                item = visible_item(item_name)
                if item and not self._hand_items_from_snapshot(world_snapshot):
                    redirect("READY", item["name"], f"Prepared {item['name']} from the visible slot before use.")
                else:
                    wait("USE requires the named item to be in your hand.")

        elif action == "ASSEMBLE":
            recipes = world_snapshot.get("available_recipes", [])
            recipe = next((entry for entry in recipes if self._label_matches(target, str(entry.get("id", ""))) or self._label_matches(target, str(entry.get("name", "")))), None)
            if self._hand_items_from_snapshot(world_snapshot):
                held = self._hand_items_from_snapshot(world_snapshot)[0]
                occupied_visible = any(str(item.get("inventory_slot", "")) == "visible" for item in world_snapshot.get("agent_inventory", []))
                if not occupied_visible:
                    redirect("STOW", held["name"], f"Stowed {held['name']} to free a hand for assembly.")
                else:
                    wait("ASSEMBLE needs a free hand and the visible slot is occupied; DROP or CONCEAL an item first.")
            elif not recipe:
                wait("That recipe is not available at this location.")

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

        decision["structured_output_status"] = (
            self.STRUCTURED_STATUS_VALIDATED_CORRECTED if corrected else self.STRUCTURED_STATUS_VALIDATED
        )
        return decision

    def _goal_permits_sabotage(self) -> bool:
        """Keep destructive powers available to explicitly disruptive goals only."""
        goal = self.secret_goal.lower()
        destructive = ("sabotage", "offline", "disable", "disrupt", "chaos", "failure", "evacuat")
        protective = ("keep", "protect", "restore", "repair", "maintain", "stabil", "functional", "contain", "identify")
        return any(token in goal for token in destructive) or not any(token in goal for token in protective)

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
        system_prompt = self._build_system_prompt(snapshot)

        user_prompt = f"Current Situation:\n{observation}\n\nWhat do you do next?"

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

        normalized = self._normalize_decision({})
        return self._validate_decision_against_telemetry(normalized, snapshot)

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

        response = self.strategic_client.chat.completions.create(
            model=self.strategic_reasoning_model,
            messages=[{"role": "user", "content": reflection_prompt}]
        )

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

        self.memory_buffer = []  # Clear buffer after consolidation
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
            return {"source": "fallback", "plan": {}, "error": str(exc)[:240]}

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
