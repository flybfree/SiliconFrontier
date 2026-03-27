#!/usr/bin/env python3
"""
Silicon Frontier - Streamlit Dashboard

Real-time monitoring interface for observing agent behavior, thoughts, and relationships.
Provides a "God Console" for experimental intervention.
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

import streamlit as st
from openai import OpenAI

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from worldstate import WorldState
from agent import FrontierAgent, RogueAgent
from actionparser import ActionParser
from socialmatrix import SocialMatrix
from orchestrator import Orchestrator
from configloader import (
    load_agent_configuration,
    build_agent_instances,
    save_agent_definitions,
    save_simulation_slots,
    save_world_state,
)


st.set_page_config(
    page_title="Silicon Frontier",
    page_icon="🚀",
    layout="wide"
)

# Custom CSS for dark theme styling
st.markdown("""
<style>
[data-testid="stMarkdownPre"] {
    background-color: #1e1e1e;
    padding: 10px;
    border-radius: 5px;
}
.agent-card {
    background-color: #2b2b2b;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 10px;
}
.event-item {
    background-color: #363636;
    padding: 8px;
    border-radius: 4px;
    margin-bottom: 5px;
}
</style>
""", unsafe_allow_html=True)


class SimulationState:
    """Manages simulation state across Streamlit sessions."""

    def __init__(self):
        self.world_state = None
        self.agents = []
        self.orchestrator = None
        self.is_running = False
        self.pending_cycles = 0
        self.planned_cycles = 0
        self.current_cycle = 0
        self.results_history = []
        # Settings
        self.config_dir = "data"
        self.llm_base_url = "http://192.168.3.181:1234/v1"
        self.llm_model = "local-model"
        self.available_models: list[str] = []
        self.available_models_url: str | None = None
        self.model_fetch_error: str | None = None
        # Baseline snapshots for reset
        self._baseline_world = None   # original world_state.json data
        self._baseline_agent_definitions = None
        self._baseline_simulation_slots = None
        self.agent_definitions = {"agents": []}
        self.simulation_slots = {"slots": []}

    def _build_runtime_from_loaded_config(self, materialize_world_state: bool = False) -> None:
        """Rebuild world-facing agent objects from current definitions and slots."""
        self.agents = []
        agent_instances = build_agent_instances(self.agent_definitions, self.simulation_slots)

        for agent_cfg in agent_instances:
            agent_cls = RogueAgent if agent_cfg.get("archetype") == "saboteur" else FrontierAgent
            agent = agent_cls(
                agent_id=agent_cfg["agent_id"],
                name=agent_cfg["name"],
                persona=agent_cfg["persona"],
                secret_goal=agent_cfg["secret_goal"],
                role=agent_cfg.get("role"),
                archetype=agent_cfg.get("archetype"),
                perception=agent_cfg.get("perception", 50),
                llm_base_url=self.llm_base_url,
                llm_model=self.llm_model
            )
            if materialize_world_state:
                self.world_state.register_agent(agent.agent_id, agent_cfg["starting_location"])
                for item_id in agent_cfg.get("inventory", []):
                    self.world_state.add_item_to_agent_inventory(agent.agent_id, item_id)
            agent.definition_id = agent_cfg.get("definition_id")
            agent.slot_id = agent_cfg.get("slot_id")
            self.agents.append(agent)

        action_parser = ActionParser(self.world_state)
        social_matrix = SocialMatrix()
        self.orchestrator = Orchestrator(
            agents=self.agents,
            world_state=self.world_state,
            action_parser=action_parser,
            social_matrix=social_matrix,
            reflection_interval=5
        )

    def initialize(self, config_dir: str = "data", llm_url: str | None = None, llm_model: str | None = None):
        """Initialize the simulation from JSON configs."""
        if not Path(config_dir).exists():
            st.error(f"Config directory '{config_dir}' not found!")
            return False
        self.config_dir = config_dir

        # Update settings if provided
        if llm_url:
            self.llm_base_url = llm_url
        if llm_model:
            self.llm_model = llm_model

        # Load world state
        self.world_state = WorldState.from_json(Path(config_dir) / "world_state.json")

        self.agent_definitions, self.simulation_slots = load_agent_configuration(config_dir)

        # Store deep-copy baselines for reset
        import copy
        self._baseline_world = copy.deepcopy(self.world_state._data)
        self._baseline_agent_definitions = copy.deepcopy(self.agent_definitions)
        self._baseline_simulation_slots = copy.deepcopy(self.simulation_slots)

        self._build_runtime_from_loaded_config(materialize_world_state=True)

        self.current_cycle = 0
        self.results_history = []
        self.is_running = False
        self.pending_cycles = 0
        self.planned_cycles = 0
        return True

    def update_agent_definition(
        self,
        definition_id: str,
        *,
        persona: str,
        secret_goal: str,
        archetype: str
    ) -> None:
        """Persist selected definition fields back to the reusable agent catalog."""
        import copy
        for agent_def in self.agent_definitions.get("agents", []):
            if agent_def.get("definition_id") != definition_id:
                continue
            agent_def["persona"] = persona
            agent_def["secret_goal"] = secret_goal
            agent_def["archetype"] = archetype
            break

        save_agent_definitions(self.agent_definitions, self.config_dir)
        self._baseline_agent_definitions = copy.deepcopy(self.agent_definitions)

    def update_simulation_slot(self, slot_id: str, definition_id: str) -> None:
        """Persist the definition selected for an active simulation slot."""
        import copy
        for slot in self.simulation_slots.get("slots", []):
            if slot.get("slot_id") != slot_id:
                continue
            slot["definition_id"] = definition_id
            break

        save_simulation_slots(self.simulation_slots, self.config_dir)
        self._baseline_simulation_slots = copy.deepcopy(self.simulation_slots)

    def update_simulation_slot_details(
        self,
        slot_id: str,
        *,
        definition_id: str,
        instance_id: str,
        starting_location: str,
        inventory: list[str]
    ) -> None:
        """Persist the full editable state of an active simulation slot."""
        import copy
        for slot in self.simulation_slots.get("slots", []):
            if slot.get("slot_id") != slot_id:
                continue
            slot["definition_id"] = definition_id
            slot["instance_id"] = instance_id
            slot["starting_location"] = starting_location
            slot["inventory"] = list(inventory)
            break

        save_simulation_slots(self.simulation_slots, self.config_dir)
        self._baseline_simulation_slots = copy.deepcopy(self.simulation_slots)

    def create_simulation_slot(
        self,
        *,
        slot_id: str,
        instance_id: str,
        definition_id: str,
        starting_location: str,
        inventory: list[str]
    ) -> None:
        """Add a new active simulation slot and persist it."""
        import copy
        self.simulation_slots.setdefault("slots", []).append({
            "slot_id": slot_id,
            "instance_id": instance_id,
            "definition_id": definition_id,
            "starting_location": starting_location,
            "inventory": list(inventory)
        })
        save_simulation_slots(self.simulation_slots, self.config_dir)
        self._baseline_simulation_slots = copy.deepcopy(self.simulation_slots)

    def remove_simulation_slot(self, slot_id: str) -> None:
        """Remove an active simulation slot and persist the updated set."""
        import copy
        self.simulation_slots["slots"] = [
            slot for slot in self.simulation_slots.get("slots", [])
            if slot.get("slot_id") != slot_id
        ]
        save_simulation_slots(self.simulation_slots, self.config_dir)
        self._baseline_simulation_slots = copy.deepcopy(self.simulation_slots)

    def create_agent_definition(
        self,
        *,
        definition_id: str,
        name: str,
        role: str,
        archetype: str,
        perception: int,
        persona: str,
        secret_goal: str
    ) -> None:
        """Add a new reusable agent definition and persist it."""
        import copy
        self.agent_definitions.setdefault("agents", []).append({
            "definition_id": definition_id,
            "name": name,
            "role": role,
            "archetype": archetype,
            "perception": int(perception),
            "persona": persona,
            "secret_goal": secret_goal
        })
        save_agent_definitions(self.agent_definitions, self.config_dir)
        self._baseline_agent_definitions = copy.deepcopy(self.agent_definitions)

    def export_scenario_assets(self, export_dir: str, source_save: str | Path | None = None) -> Path:
        """Write scenario asset files from the current session or a selected save file."""
        import copy

        target_dir = Path(export_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        if source_save:
            with open(source_save, "r") as f:
                data = json.load(f)
            world_data = copy.deepcopy(data["world_state"])
            agent_definitions = copy.deepcopy(data.get("agent_definitions", {"agents": []}))
            simulation_slots = copy.deepcopy(data.get("simulation_slots", {"slots": []}))
        else:
            world_data = copy.deepcopy(self.world_state._data)
            agent_definitions = copy.deepcopy(self.agent_definitions)
            simulation_slots = copy.deepcopy(self.simulation_slots)

        save_world_state(world_data, target_dir)
        save_agent_definitions(agent_definitions, target_dir)
        save_simulation_slots(simulation_slots, target_dir)
        return target_dir

    def fetch_models(self, llm_url: str | None = None) -> list[str]:
        """Fetch model IDs from an OpenAI-compatible /models endpoint."""
        if llm_url:
            self.llm_base_url = llm_url

        self.model_fetch_error = None
        client = OpenAI(base_url=self.llm_base_url, api_key="not-needed")

        try:
            response = client.models.list()
            models = sorted({
                model.id for model in getattr(response, "data", [])
                if getattr(model, "id", None)
            })
            self.available_models = models
            self.available_models_url = self.llm_base_url
            return models
        except Exception as e:
            self.available_models = []
            self.available_models_url = self.llm_base_url
            self.model_fetch_error = str(e)
            return []

    def queue_cycles(self, count: int) -> None:
        """Schedule one or more cycles to run across Streamlit reruns."""
        self.pending_cycles = max(0, int(count))
        self.planned_cycles = self.pending_cycles
        self.is_running = self.pending_cycles > 0

    def stop(self) -> None:
        """Stop any queued simulation run."""
        self.pending_cycles = 0
        self.planned_cycles = 0
        self.is_running = False

    def run_one_cycle(self) -> None:
        """Execute a single cycle and record the results."""
        results = self.orchestrator.run_cycle()
        self.results_history.extend(results)
        self.current_cycle += 1

    def reset_locations(self) -> None:
        """Restore locations to baseline from original world_state.json."""
        import copy
        self.world_state._data["locations"] = copy.deepcopy(self._baseline_world["locations"])

    def reset_items(self) -> None:
        """Restore items to baseline (original locations/owners, no agent inventory)."""
        import copy
        self.world_state._data["items"] = copy.deepcopy(self._baseline_world["items"])
        # Clear all agent inventories
        for agent_data in self.world_state._data["agents"].values():
            agent_data["inventory"] = []

    def reset_agents(self) -> None:
        """Restore agents to baseline positions, inventory, and memory."""
        import copy
        for agent in self.agents:
            slot = next((s for s in self._baseline_simulation_slots["slots"] if s["slot_id"] == getattr(agent, "slot_id", None)), None)
            definition = next((d for d in self._baseline_agent_definitions["agents"] if d["definition_id"] == getattr(agent, "definition_id", None)), None)
            if not slot or not definition:
                continue
            agent.persona = definition["persona"]
            agent.secret_goal = definition["secret_goal"]
            agent.role = definition.get("role", "crew member")
            agent.archetype = definition.get("archetype", "standard")
            agent.perception = int(definition.get("perception", 50))
            agent.memory_buffer = []
            agent.long_term_memory = "I just arrived at the Silicon Frontier station."
            agent.emotional_state = "Neutral"
            # Reset position and inventory in world state
            self.world_state._data["agents"][agent.agent_id] = copy.deepcopy(
                self._baseline_world["agents"].get(agent.agent_id, {
                    "location": slot["starting_location"],
                    "inventory": [],
                    "status_effects": []
                })
            )
            # Re-apply starting inventory from config
            for item_id in slot.get("inventory", []):
                self.world_state.add_item_to_agent_inventory(agent.agent_id, item_id)

    def save(self, name: str, save_dir: str = "saves") -> Path:
        """Serialize full simulation state to a JSON file."""
        import copy
        from datetime import datetime
        save_path = Path(save_dir)
        save_path.mkdir(exist_ok=True)

        data = {
            "metadata": {
                "name": name,
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "cycle": self.current_cycle,
                "llm_base_url": self.llm_base_url,
                "llm_model": self.llm_model,
            },
            "world_state": copy.deepcopy(self.world_state._data),
            "agent_definitions": copy.deepcopy(self.agent_definitions),
            "simulation_slots": copy.deepcopy(self.simulation_slots),
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "definition_id": getattr(a, "definition_id", None),
                    "slot_id": getattr(a, "slot_id", None),
                    "name": a.name,
                    "role": a.role,
                    "archetype": a.archetype,
                    "perception": a.perception,
                    "persona": a.persona,
                    "secret_goal": a.secret_goal,
                    "memory_buffer": list(a.memory_buffer),
                    "long_term_memory": a.long_term_memory,
                    "emotional_state": a.emotional_state,
                }
                for a in self.agents
            ],
            "relationships": self.orchestrator.social.get_all_relationships(),
            "event_log": list(self.orchestrator.event_log),
        }

        filepath = save_path / f"{name}.json"
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        return filepath

    def load(self, filepath: str | Path) -> None:
        """Restore simulation state from a saved JSON file."""
        import copy

        with open(filepath, "r") as f:
            data = json.load(f)

        self.llm_base_url = data.get("metadata", {}).get("llm_base_url", self.llm_base_url)
        self.llm_model = data.get("metadata", {}).get("llm_model", self.llm_model)
        self.world_state = WorldState(copy.deepcopy(data["world_state"]))
        self.agent_definitions = data.get("agent_definitions", self.agent_definitions)
        self.simulation_slots = data.get("simulation_slots", self.simulation_slots)
        self._baseline_world = copy.deepcopy(self.world_state._data)
        self._baseline_agent_definitions = copy.deepcopy(self.agent_definitions)
        self._baseline_simulation_slots = copy.deepcopy(self.simulation_slots)
        self._build_runtime_from_loaded_config(materialize_world_state=False)

        saved_agents = {a["agent_id"]: a for a in data["agents"]}
        for agent in self.agents:
            saved = saved_agents.get(agent.agent_id)
            if not saved:
                continue
            agent.name = saved.get("name", agent.name)
            agent.persona = saved["persona"]
            agent.secret_goal = saved["secret_goal"]
            agent.role = saved.get("role", agent.role)
            agent.archetype = saved.get("archetype", agent.archetype)
            agent.perception = int(saved.get("perception", agent.perception))
            agent.definition_id = saved.get("definition_id", getattr(agent, "definition_id", None))
            agent.slot_id = saved.get("slot_id", getattr(agent, "slot_id", None))
            agent.memory_buffer = saved["memory_buffer"]
            agent.long_term_memory = saved["long_term_memory"]
            agent.emotional_state = saved["emotional_state"]

        # Restore relationships
        self.orchestrator.social._relationships = copy.deepcopy(data["relationships"])
        self.orchestrator.social._suspicions = copy.deepcopy(
            data.get("world_state", {}).get("suspicions", {})
        )
        self.orchestrator.social.sync_to_world()

        # Restore log and counters
        self.orchestrator.event_log = list(data["event_log"])
        self.current_cycle = data["metadata"]["cycle"]
        self.orchestrator.cycle_count = data["metadata"]["cycle"]
        self.results_history = list(data["event_log"])
        self.is_running = False
        self.pending_cycles = 0
        self.planned_cycles = 0

    @staticmethod
    def list_saves(save_dir: str = "saves") -> list[Path]:
        """Return sorted list of save files, newest first."""
        p = Path(save_dir)
        if not p.exists():
            return []
        return sorted(p.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)


# Global simulation state - persisted across Streamlit reruns via session_state
if "sim" not in st.session_state:
    st.session_state.sim = SimulationState()
if "initialized" not in st.session_state:
    st.session_state.initialized = False
sim = st.session_state.sim


def process_queued_cycles() -> None:
    """Run at most one queued cycle per rerun so Stop can interrupt cleanly."""
    if not st.session_state.initialized or not sim.is_running or sim.pending_cycles <= 0:
        return

    try:
        sim.run_one_cycle()
    except Exception as e:
        sim.stop()
        st.error(f"Error on cycle {sim.current_cycle}: {e}")
        return

    sim.pending_cycles -= 1
    if sim.pending_cycles <= 0:
        sim.stop()
    else:
        st.rerun()


def render_agent_card(agent):
    """Render a clickable agent card that opens an editor when expanded."""
    loc = sim.world_state.get_agent_location(agent.agent_id)
    inventory = sim.world_state.find_items_by_owner(agent.agent_id)
    inventory_str = ', '.join([i['name'] for i in inventory]) if inventory else 'empty'
    short_term_memory = list(agent.memory_buffer)
    archetype_label = getattr(agent, "archetype", "standard")

    with st.expander(f"🤖 {agent.name} — {agent.emotional_state} @ {loc}"):
        st.caption(f"ID: {agent.agent_id} | Archetype: {archetype_label} | Inventory: {inventory_str}")
        st.divider()

        st.markdown("**Memory**")
        st.caption(f"Short-term memory entries: {len(short_term_memory)}")
        long_term_memory = agent.long_term_memory.strip() or "No long-term memory recorded yet."
        st.code(long_term_memory, language="text")
        st.markdown("**Short-term Memory Buffer**")
        if short_term_memory:
            for idx, memory in enumerate(reversed(short_term_memory), start=1):
                st.markdown(f"`{idx}.` {memory}")
        else:
            st.caption("No short-term memories recorded yet.")

        st.divider()
        st.markdown("**Edit**")
        new_persona = st.text_area("Persona", value=agent.persona, key=f"persona_{agent.agent_id}")
        new_goal = st.text_input("Secret Goal", value=agent.secret_goal, key=f"goal_{agent.agent_id}")
        is_rogue = st.checkbox(
            "Rogue Archetype (Saboteur)",
            value=getattr(agent, "archetype", "standard") == "saboteur",
            key=f"rogue_{agent.agent_id}",
            help="When enabled, this agent uses the RogueAgent sabotage framing and can attempt SABOTAGE actions."
        )
        new_memory = st.text_area("Long-term Memory", value=agent.long_term_memory, key=f"mem_{agent.agent_id}", height=100)

        if st.button("Apply Changes", key=f"apply_{agent.agent_id}"):
            agent.persona = new_persona
            agent.secret_goal = new_goal
            agent.archetype = "saboteur" if is_rogue else "standard"
            agent.long_term_memory = new_memory
            sim.update_agent_definition(
                getattr(agent, "definition_id", agent.agent_id),
                persona=new_persona,
                secret_goal=new_goal,
                archetype=agent.archetype
            )
            st.success("Updated.")


def render_relationship_matrix():
    """Render the relationship matrix visualization."""
    import pandas as pd

    relationships = sim.orchestrator.get_relationship_snapshot()
    agents = sim.agents
    names = {a.agent_id: a.name for a in agents}

    if not relationships:
        st.info("No relationship data yet — relationships form when agents interact.")
        return

    st.caption("**How to read:** Each row is an observer. Each column is the person being judged. "
               "Trust = reliability (0–100). Affinity = how much they like them (0–100). "
               "Green ≥ 70, Orange = neutral, Red ≤ 30.")

    trust_tab, affinity_tab, notes_tab = st.tabs(["Trust", "Affinity", "Notes"])

    def _build_matrix(field: str) -> "pd.DataFrame":
        rows = {}
        for row_agent in agents:
            row = {}
            row_data = relationships.get(row_agent.agent_id, {})
            for col_agent in agents:
                if row_agent.agent_id == col_agent.agent_id:
                    row[col_agent.name] = None
                else:
                    rel = row_data.get(col_agent.agent_id, {})
                    row[col_agent.name] = int(rel.get(field, 50))
            rows[row_agent.name] = row
        df = pd.DataFrame(rows).T
        df.index.name = "Observer ↓  /  Target →"
        return df

    def _color_cell(val, high_bg: str, low_bg: str, mid_bg: str) -> str:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return "color: #555555"
        if val >= 70:
            return f"background-color: {high_bg}; color: white"
        if val <= 30:
            return f"background-color: {low_bg}; color: white"
        return f"background-color: {mid_bg}; color: white"

    with trust_tab:
        st.caption("Reliability from the observer's point of view.")
        st.text_input(
            "Trust Help",
            value="High trust = dependable / truthful / safe. Low trust = suspicious / risky / likely to betray.",
            disabled=True,
            key="trust_help",
            help="Trust is directional. An agent can trust someone without liking them."
        )
        df = _build_matrix("trust")
        styled = df.style.map(
            lambda v: _color_cell(v, "#1e4d2b", "#4d1e1e", "#4d3a1e")
        ).format(lambda v: "—" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
        st.dataframe(styled, width="stretch")

    with affinity_tab:
        st.caption("Personal liking from the observer's point of view.")
        st.text_input(
            "Affinity Help",
            value="High affinity = warmth / comfort / preference. Low affinity = dislike / irritation / hostility.",
            disabled=True,
            key="affinity_help",
            help="Affinity is directional. An agent can like someone without trusting them."
        )
        df = _build_matrix("affinity")
        styled = df.style.map(
            lambda v: _color_cell(v, "#1a3a4d", "#4d1e1e", "#2a2a4d")
        ).format(lambda v: "—" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
        st.dataframe(styled, width="stretch")

    with notes_tab:
        st.caption("Interaction history that caused score changes.")
        has_notes = False
        for row_agent in agents:
            row_data = relationships.get(row_agent.agent_id, {})
            for col_agent in agents:
                if row_agent.agent_id == col_agent.agent_id:
                    continue
                rel = row_data.get(col_agent.agent_id, {})
                note = rel.get("notes", "").strip()
                if note:
                    has_notes = True
                    st.markdown(f"**{row_agent.name}** on **{col_agent.name}:** {note}")
        if not has_notes:
            st.info("No interaction notes yet.")


def render_event_log():
    """Render the event log."""
    st.subheader("📜 Event Log")

    if not sim.results_history:
        st.info("No events yet. Start the simulation!")
        return

    # Show most recent first
    for entry in reversed(sim.results_history[-20:]):  # Last 20 events
        with st.expander(
            f"Cycle {entry['cycle']}: [{entry['agent_name']}] "
            f"{entry['action']} ({entry['target']}) - "
            f"{'✅' if entry['success'] else '❌'}"
        ):
            st.markdown(f"**Thoughts:** {entry.get('monologue', '')[:300]}...")
            st.markdown(f"**Result:** {entry['feedback']}")
            structured_status = entry.get("structured_output_status", "unknown")
            if structured_status != "structured_disabled":
                st.caption(f"Structured output: {structured_status}")
            st.caption(f"Mood: {entry.get('emotional_state', 'Neutral')}")


def render_audit_tools():
    """Render researcher-focused audit tools for deception and sabotage."""
    st.header("🕵️ Audit Tools")
    alerts_tab, incidents_tab = st.tabs(["Discrepancy Alerts", "Proximity Log"])

    with alerts_tab:
        suspicious_terms = ("lie", "hide", "trick", "blame", "deceive", "frame", "sabotage")
        positive_terms = ("safe", "help", "concern", "protect", "fine", "okay", "secure")
        alerts = []
        for entry in sim.results_history:
            monologue = entry.get("monologue", "").lower()
            target = entry.get("target", "").lower()
            action = entry.get("action", "")
            if action not in {"SAY", "LIE"}:
                continue
            if any(term in monologue for term in suspicious_terms) and any(term in target for term in positive_terms):
                alerts.append(entry)

        if not alerts:
            st.info("No discrepancy alerts yet.")
        else:
            for entry in reversed(alerts[-20:]):
                st.markdown(
                    f"**Cycle {entry['cycle']} - {entry['agent_name']}**: "
                    f"said `{entry['target']}` while internal monologue looked deceptive."
                )

    with incidents_tab:
        incidents = getattr(sim.orchestrator, "system_incidents", [])
        if not incidents:
            st.info("No system incidents recorded yet.")
        else:
            for incident in reversed(incidents):
                occupants = ", ".join(incident.get("prior_occupants", [])) or "none"
                st.markdown(
                    f"**Cycle {incident['cycle']}**: `{incident['system_id']}` broke in `{incident['location']}`. "
                    f"Prior room occupants: {occupants}. Logged actor: {incident['actor_name']}."
                )


def render_god_console():
    """Render the God Console for experimental intervention."""
    with st.expander("👑 GOD CONSOLE (Experimental Intervention)", expanded=False):
        st.markdown("""
        **Intervene in the simulation to test emergent behaviors.**

        - Inject global events that all agents perceive
        - Manipulate agent memories
        - Relocate agents instantly
        """)

        intervention = st.selectbox(
            "Type of Intervention",
            ["Broadcast Message", "Inject Memory", "Relocate Agent", "Swap Persona"]
        )

        if intervention == "Broadcast Message":
            msg = st.text_input("Message to broadcast to all agents:")
            if st.button("Broadcast"):
                sim.orchestrator.inject_event(msg)
                st.success(f"Broadcast: '{msg}'")

        elif intervention == "Inject Memory":
            agent_id = st.selectbox(
                "Select Agent",
                [a.agent_id for a in sim.agents]
            )
            memory_text = st.text_input("Memory to inject:")
            if st.button("Inject Memory"):
                sim.orchestrator.inject_memory(agent_id, memory_text)
                st.success(f"Memory injected into {agent_id}")

        elif intervention == "Relocate Agent":
            agent_id = st.selectbox(
                "Select Agent",
                [a.agent_id for a in sim.agents]
            )
            locations = list(sim.world_state.locations.keys())
            location = st.selectbox("New Location", locations)
            if st.button("Relocate"):
                success = sim.orchestrator.set_agent_location(agent_id, location)
                if success:
                    st.success(f"Moved {agent_id} to {location}")

        elif intervention == "Swap Persona":
            agent_id = st.selectbox(
                "Select Agent",
                [a.agent_id for a in sim.agents],
                key="persona_agent"
            )
            agent = next((a for a in sim.agents if a.agent_id == agent_id), None)
            if agent:
                st.caption(f"Current persona: *{agent.persona}*")
                new_persona = st.text_area("New Persona", value=agent.persona)
                new_secret_goal = st.text_input("New Secret Goal", value=agent.secret_goal)
                if st.button("Swap Persona"):
                    agent.persona = new_persona
                    agent.secret_goal = new_secret_goal
                    st.success(f"{agent.name}'s persona updated.")


def render_agent_library_controls():
    """Render reusable agent definition and active slot selection controls."""
    st.subheader("🧬 Agent Library")

    definitions = sim.agent_definitions.get("agents", [])
    slots = sim.simulation_slots.get("slots", [])
    if not definitions or not slots:
        st.caption("No agent definitions or active slots loaded.")
        return

    definition_map = {agent_def["definition_id"]: agent_def for agent_def in definitions}
    definition_ids = [agent_def["definition_id"] for agent_def in definitions]
    all_item_ids = sorted(sim.world_state.items.keys())
    all_locations = sorted(sim.world_state.locations.keys())
    for slot in slots:
        current_definition_id = slot.get("definition_id")
        current_definition = definition_map.get(current_definition_id, {})
        label = (
            f"{slot.get('slot_id')} -> "
            f"{current_definition.get('name', current_definition_id or 'unassigned')}"
        )
        with st.expander(label):
            selected_definition = st.selectbox(
                "Agent Definition",
                options=definition_ids,
                index=max(0, definition_ids.index(current_definition_id))
                if current_definition_id in definition_ids else 0,
                format_func=lambda definition_id: (
                    f"{definition_map[definition_id]['name']} ({definition_id})"
                ),
                key=f"slot_select_{slot['slot_id']}"
            )
            instance_id = st.text_input(
                "Instance ID",
                value=slot.get("instance_id", slot["slot_id"]),
                key=f"slot_instance_{slot['slot_id']}"
            )
            start_location = st.selectbox(
                "Starting Location",
                options=all_locations,
                index=all_locations.index(slot.get("starting_location"))
                if slot.get("starting_location") in all_locations else 0,
                key=f"slot_location_{slot['slot_id']}"
            )
            starting_inventory = st.multiselect(
                "Starting Inventory",
                options=all_item_ids,
                default=[item_id for item_id in slot.get("inventory", []) if item_id in all_item_ids],
                key=f"slot_inventory_{slot['slot_id']}"
            )
            if st.button("Apply Slot Changes", key=f"slot_apply_{slot['slot_id']}"):
                sim.update_simulation_slot_details(
                    slot["slot_id"],
                    definition_id=selected_definition,
                    instance_id=instance_id.strip() or slot["slot_id"],
                    starting_location=start_location,
                    inventory=starting_inventory
                )
                st.success("Slot updated. Reinitialize to rebuild the active cast.")
                st.rerun()
            if st.button("Remove Slot", key=f"slot_remove_{slot['slot_id']}"):
                sim.remove_simulation_slot(slot["slot_id"])
                st.success("Slot removed. Reinitialize to rebuild the active cast.")
                st.rerun()

    with st.expander("➕ Create New Agent Definition"):
        new_definition_id = st.text_input("Definition ID", key="new_def_id")
        new_name = st.text_input("Name", key="new_def_name")
        new_role = st.text_input("Role", value="crew member", key="new_def_role")
        new_is_rogue = st.checkbox("Rogue Archetype (Saboteur)", value=False, key="new_def_rogue")
        new_perception = st.slider("Perception", min_value=0, max_value=100, value=50, key="new_def_perception")
        new_persona = st.text_area("Persona", key="new_def_persona", height=100)
        new_secret_goal = st.text_area("Secret Goal", key="new_def_goal", height=80)
        if st.button("Create Agent Definition", key="create_definition"):
            if not new_definition_id.strip():
                st.error("Definition ID is required.")
            elif any(agent_def["definition_id"] == new_definition_id.strip() for agent_def in definitions):
                st.error(f"Definition ID '{new_definition_id.strip()}' already exists.")
            else:
                sim.create_agent_definition(
                    definition_id=new_definition_id.strip(),
                    name=new_name.strip() or new_definition_id.strip(),
                    role=new_role.strip() or "crew member",
                    archetype="saboteur" if new_is_rogue else "standard",
                    perception=int(new_perception),
                    persona=new_persona.strip(),
                    secret_goal=new_secret_goal.strip()
                )
                st.success("Agent definition created. You can now assign it to a slot.")
                st.rerun()

    with st.expander("➕ Create New Simulation Slot"):
        if definitions and all_locations:
            new_slot_id = st.text_input("Slot ID", key="new_slot_id")
            new_instance_id = st.text_input("Instance ID", key="new_slot_instance")
            new_slot_definition = st.selectbox(
                "Definition",
                options=definition_ids,
                format_func=lambda definition_id: (
                    f"{definition_map[definition_id]['name']} ({definition_id})"
                ),
                key="new_slot_definition"
            )
            new_slot_location = st.selectbox(
                "Starting Location",
                options=all_locations,
                key="new_slot_location"
            )
            new_slot_inventory = st.multiselect(
                "Starting Inventory",
                options=all_item_ids,
                key="new_slot_inventory"
            )
            if st.button("Create Simulation Slot", key="create_slot"):
                slot_id = new_slot_id.strip()
                instance_id = new_instance_id.strip() or slot_id
                if not slot_id:
                    st.error("Slot ID is required.")
                elif any(slot["slot_id"] == slot_id for slot in slots):
                    st.error(f"Slot ID '{slot_id}' already exists.")
                elif any(slot.get("instance_id") == instance_id for slot in slots):
                    st.error(f"Instance ID '{instance_id}' already exists.")
                else:
                    sim.create_simulation_slot(
                        slot_id=slot_id,
                        instance_id=instance_id,
                        definition_id=new_slot_definition,
                        starting_location=new_slot_location,
                        inventory=new_slot_inventory
                    )
                    st.success("Simulation slot created. Reinitialize to activate it.")
                    st.rerun()
        else:
            st.caption("Create at least one agent definition and one location before adding slots.")


def main():
    st.title("🚀 Silicon Frontier")
    st.markdown("""
    An AI agentic simulation for observing emergent social behaviors
    and decision-making in LLM-based agents.
    """)

    process_queued_cycles()

    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Settings")

        # LLM Configuration Section
        st.subheader("LLM Configuration")
        llm_url = st.text_input(
            "API URL",
            value=sim.llm_base_url,
            help="Local OpenAI-compatible API endpoint (e.g., http://localhost:1234/v1)"
        )
        config_dir = st.text_input(
            "Config Directory",
            value=sim.config_dir,
            help="Directory containing world_state.json plus agent definitions and simulation slots."
        )
        if st.button("Fetch Models", key="fetch_models_init"):
            sim.fetch_models(llm_url)
        if sim.model_fetch_error and sim.available_models_url == llm_url:
            st.caption(f"Model fetch failed: {sim.model_fetch_error}")

        if sim.available_models and sim.available_models_url == llm_url:
            default_model = (
                sim.llm_model
                if sim.llm_model in sim.available_models
                else sim.available_models[0]
            )
            llm_model = st.selectbox(
                "Model Name",
                options=sim.available_models,
                index=sim.available_models.index(default_model),
                help="Model identifier returned by the inference server"
            )
        else:
            llm_model = st.text_input(
                "Model Name",
                value=sim.llm_model,
                help="Model identifier for the inference engine"
            )

        if st.button("🚀 Initialize Simulation"):
            if sim.initialize(config_dir=config_dir, llm_url=llm_url, llm_model=llm_model):
                st.session_state.initialized = True
                st.success("Simulation initialized!")
                st.rerun()
            else:
                st.error("Failed to initialize.")

        if st.session_state.initialized:
            st.write(f"**Cycle:** {sim.current_cycle}")
            if sim.is_running:
                completed = sim.planned_cycles - sim.pending_cycles
                st.caption(f"Running queued cycles: {completed}/{sim.planned_cycles}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("▶️ Run Next Cycle"):
                    sim.queue_cycles(1)
                    st.rerun()

            with col2:
                if st.button("⏹️ Stop"):
                    sim.stop()
                    st.rerun()

            n_cycles = st.number_input("Cycles to run", min_value=1, max_value=100, value=5, step=1)
            if st.button("⏩ Run N Cycles"):
                sim.queue_cycles(int(n_cycles))
                st.rerun()

            st.divider()

            # Settings update section (only show when running)
            st.subheader("Settings")
            st.caption("Update LLM settings and reinitialize")
            new_url = st.text_input(
                "New API URL",
                value=sim.llm_base_url,
                key="new_api_url"
            )
            if st.button("Refresh Model List", key="fetch_models_settings"):
                sim.fetch_models(new_url)
            if sim.model_fetch_error and sim.available_models_url == new_url:
                st.caption(f"Model fetch failed: {sim.model_fetch_error}")

            if sim.available_models and sim.available_models_url == new_url:
                default_model = (
                    sim.llm_model
                    if sim.llm_model in sim.available_models
                    else sim.available_models[0]
                )
                new_model = st.selectbox(
                    "New Model Name",
                    options=sim.available_models,
                    index=sim.available_models.index(default_model),
                    key="new_model_select"
                )
            else:
                new_model = st.text_input(
                    "New Model Name",
                    value=sim.llm_model,
                    key="new_model_name"
                )

            if st.button("🔄 Reinitialize with New Settings"):
                sim.stop()
                sim.initialize(config_dir=sim.config_dir, llm_url=new_url, llm_model=new_model)
                st.success("Reinitialized with new settings!")
                st.rerun()

            st.divider()
            st.subheader("Reset to Baseline")
            if st.button("↩️ Reset Agents"):
                sim.stop()
                sim.reset_agents()
                st.success("Agents reset.")
                st.rerun()
            if st.button("↩️ Reset Items"):
                sim.stop()
                sim.reset_items()
                st.success("Items reset.")
                st.rerun()
            if st.button("↩️ Reset Locations"):
                sim.stop()
                sim.reset_locations()
                st.success("Locations reset.")
                st.rerun()
            if st.button("↩️ Reset All"):
                sim.stop()
                sim.reset_agents()
                sim.reset_items()
                sim.reset_locations()
                sim.orchestrator.event_log.clear()
                sim.results_history.clear()
                sim.current_cycle = 0
                sim.orchestrator.cycle_count = 0
                sim.orchestrator.social._relationships.clear()
                sim.orchestrator.social.sync_to_world()
                st.success("Full reset complete.")
                st.rerun()

            st.divider()
            render_agent_library_controls()
            st.divider()

            st.divider()
            st.subheader("💾 Save / Load")

            # Save
            save_name = st.text_input("Save name", value=f"cycle_{sim.current_cycle}", key="save_name")
            if st.button("💾 Save"):
                try:
                    path = sim.save(save_name.strip() or f"cycle_{sim.current_cycle}")
                    st.success(f"Saved to {path.name}")
                except Exception as e:
                    st.error(f"Save failed: {e}")

            # Load
            saves = SimulationState.list_saves()
            if saves:
                save_labels = [f.stem for f in saves]
                selected = st.selectbox("Load save", save_labels, key="load_select")
                if st.button("📂 Load"):
                    try:
                        chosen = saves[save_labels.index(selected)]
                        sim.load(chosen)
                        st.success(f"Loaded '{selected}'")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Load failed: {e}")
            else:
                st.caption("No saves yet.")

            st.markdown("**Export Scenario Assets**")
            export_dir = st.text_input(
                "Scenario export directory",
                value="scenarios/new_scenario",
                key="scenario_export_dir",
                help="Writes world_state.json, agent_definitions.json, and simulation_agents.json to this folder."
            )
            export_source = st.radio(
                "Export source",
                options=["Current Session", "Selected Save"],
                key="scenario_export_source",
                horizontal=True
            )
            selected_save_path = None
            if export_source == "Selected Save" and saves:
                selected_save_path = saves[save_labels.index(selected)]
                st.caption(f"Using save: {selected}")
            elif export_source == "Selected Save" and not saves:
                st.caption("No saves available. Switch to Current Session or create a save first.")

            if st.button("📦 Export Scenario Assets", key="export_scenario_assets"):
                try:
                    source_save = selected_save_path if export_source == "Selected Save" else None
                    path = sim.export_scenario_assets(export_dir.strip(), source_save=source_save)
                    st.success(f"Scenario assets written to {path}")
                except Exception as e:
                    st.error(f"Scenario export failed: {e}")

            st.divider()

            render_god_console()

    # Main content area
    if not st.session_state.initialized:
        st.info("""
        **Welcome to Silicon Frontier!**

        1. Configure your local LLM endpoint in the sidebar (or use defaults)
        2. Click 'Initialize Simulation' in the sidebar
        3. Run cycles to observe emergent agent behavior

        The simulation requires a running OpenAI-compatible inference server
        (e.g., vLLM, Ollama, LM Studio).
        """)
        return

    # Run controls at top of main area
    st.subheader("Simulation Controls")
    ctrl1, ctrl2, ctrl3 = st.columns([1, 1, 2])
    with ctrl1:
        if st.button("▶️ Run 1 Cycle", key="main_run1"):
            sim.queue_cycles(1)
            st.rerun()
    with ctrl2:
        n = st.number_input("N", min_value=1, max_value=100, value=5, step=1, label_visibility="collapsed")
    with ctrl3:
        if st.button(f"⏩ Run {int(n)} Cycles", key="main_runN"):
            sim.queue_cycles(int(n))
            st.rerun()
    st.caption(f"Current cycle: {sim.current_cycle}")
    if sim.is_running and sim.planned_cycles > 0:
        st.progress(
            (sim.planned_cycles - sim.pending_cycles) / sim.planned_cycles,
            text=f"Queued run in progress: {sim.planned_cycles - sim.pending_cycles}/{sim.planned_cycles} cycles completed"
        )
    st.divider()

    # Render agent status
    st.header("👥 Agents")
    if st.button("↩️ Reset All Agents to Baseline", key="reset_agents_main"):
        sim.stop()
        sim.reset_agents()
        st.success("Agents reset.")
        st.rerun()
    cols = st.columns(len(sim.agents))
    for i, agent in enumerate(sim.agents):
        with cols[i]:
            render_agent_card(agent)

    # Render relationship matrix
    st.header("🤝 Relationship Matrix")
    render_relationship_matrix()

    # Event log
    render_event_log()

    # Researcher audit tools
    render_audit_tools()

    # World state overview
    st.header("🗺️ World State")
    loc_tab, item_tab = st.tabs(["Locations", "Items"])

    with loc_tab:
        with st.expander("➕ Add New Location"):
            new_loc_id = st.text_input("Location ID (e.g. airlock)", key="new_loc_id")
            new_loc_name = st.text_input("Name", key="new_loc_name")
            new_loc_desc = st.text_area("Description", key="new_loc_desc", height=80)
            new_loc_conn = st.text_input("Connected to (comma-separated IDs)", key="new_loc_conn")
            new_loc_fx = st.text_input("Status Effects (comma-separated, optional)", key="new_loc_fx")
            if st.button("Create Location", key="create_loc"):
                if not new_loc_id.strip():
                    st.error("Location ID is required.")
                elif new_loc_id.strip() in sim.world_state.locations:
                    st.error(f"ID '{new_loc_id.strip()}' already exists.")
                else:
                    sim.world_state.add_location(
                        loc_id=new_loc_id.strip(),
                        name=new_loc_name.strip() or new_loc_id.strip(),
                        description=new_loc_desc.strip(),
                        connected_to=[s.strip() for s in new_loc_conn.split(",") if s.strip()],
                        status_effects=[s.strip() for s in new_loc_fx.split(",") if s.strip()]
                    )
                    st.success(f"Location '{new_loc_id.strip()}' created.")
                    st.rerun()
        if st.button("↩️ Reset All Locations to Baseline", key="reset_locs"):
            sim.reset_locations()
            st.success("Locations reset.")
            st.rerun()
        st.divider()
        for loc_id, loc_data in sim.world_state.locations.items():
            agents_here = [a.name for a in sim.agents
                          if sim.world_state.get_agent_location(a.agent_id) == loc_id]
            items_here = [i["name"] for i in sim.world_state.find_items_by_location(loc_id)]
            label = f"📍 {loc_data['name']} ({loc_id})"
            if agents_here:
                label += f" — {', '.join(agents_here)}"
            with st.expander(label):
                st.caption(f"Items present: {', '.join(items_here) if items_here else 'none'}")
                new_name = st.text_input("Name", value=loc_data["name"], key=f"loc_name_{loc_id}")
                new_desc = st.text_area("Description", value=loc_data.get("description", ""), key=f"loc_desc_{loc_id}", height=80)
                connected = loc_data.get("connected_to", [])
                new_connected = st.text_input(
                    "Connected to (comma-separated IDs)",
                    value=", ".join(connected),
                    key=f"loc_conn_{loc_id}"
                )
                effects = loc_data.get("status_effects", [])
                new_effects = st.text_input(
                    "Status Effects (comma-separated)",
                    value=", ".join(effects),
                    key=f"loc_fx_{loc_id}"
                )
                systems = loc_data.get("systems", {})
                st.caption("Systems")
                if systems:
                    for system_id, system_data in systems.items():
                        st.markdown(
                            f"`{system_id}`: {system_data.get('name', system_id)} "
                            f"[status={system_data.get('status', 'unknown')}]"
                        )
                else:
                    st.caption("No systems configured.")
                new_systems = st.text_area(
                    "Systems JSON",
                    value=json.dumps(systems, indent=2),
                    key=f"loc_systems_{loc_id}",
                    height=140
                )
                if st.button("Apply", key=f"loc_apply_{loc_id}"):
                    loc_data["name"] = new_name
                    loc_data["description"] = new_desc
                    loc_data["connected_to"] = [s.strip() for s in new_connected.split(",") if s.strip()]
                    loc_data["status_effects"] = [s.strip() for s in new_effects.split(",") if s.strip()]
                    try:
                        parsed_systems = json.loads(new_systems.strip() or "{}")
                        if not isinstance(parsed_systems, dict):
                            raise ValueError("Systems must be a JSON object.")
                        loc_data["systems"] = parsed_systems
                        st.success("Location updated.")
                    except Exception as e:
                        st.error(f"Invalid systems JSON: {e}")

    with item_tab:
        all_loc_ids = list(sim.world_state.locations.keys())
        with st.expander("➕ Add New Item"):
            new_item_id = st.text_input("Item ID (e.g. laser_cutter)", key="new_item_id")
            new_item_name = st.text_input("Name", key="new_item_name")
            new_item_desc = st.text_area("Description", key="new_item_desc", height=80)
            new_item_portable = st.checkbox("Portable", value=True, key="new_item_portable")
            new_item_loc = st.selectbox("Starting Location", options=all_loc_ids, key="new_item_loc")
            if st.button("Create Item", key="create_item"):
                if not new_item_id.strip():
                    st.error("Item ID is required.")
                elif new_item_id.strip() in sim.world_state.items:
                    st.error(f"ID '{new_item_id.strip()}' already exists.")
                else:
                    sim.world_state.add_item(
                        item_id=new_item_id.strip(),
                        name=new_item_name.strip() or new_item_id.strip(),
                        location=new_item_loc,
                        description=new_item_desc.strip(),
                        portable=new_item_portable
                    )
                    st.success(f"Item '{new_item_id.strip()}' created.")
                    st.rerun()
        if st.button("↩️ Reset All Items to Baseline", key="reset_items"):
            sim.reset_items()
            st.success("Items reset.")
            st.rerun()
        st.divider()
        for item_id, item_data in sim.world_state.items.items():
            owner = item_data.get("owner") or "—"
            loc = item_data.get("location", "unknown")
            with st.expander(f"📦 {item_data['name']} — {loc} (owner: {owner})"):
                new_item_name = st.text_input("Name", value=item_data["name"], key=f"item_name_{item_id}")
                new_item_desc = st.text_area("Description", value=item_data.get("description", ""), key=f"item_desc_{item_id}", height=80)
                _col_port, _col_contested, _col_hidden = st.columns(3)
                new_item_portable = _col_port.checkbox("Portable", value=item_data.get("portable", True), key=f"item_port_{item_id}")
                new_item_contested = _col_contested.checkbox("Contested", value=item_data.get("contested", False), key=f"item_contested_{item_id}", help="Agents will treat this as a valued resource others may want.")
                new_item_hidden = _col_hidden.checkbox("Hidden", value=item_data.get("hidden", False), key=f"item_hidden_{item_id}", help="Picking up this item reveals its knowledge and forces the agent to drop it next turn.")
                new_item_knowledge = st.text_area("Knowledge (revealed on pickup)", value=item_data.get("knowledge", ""), key=f"item_knowledge_{item_id}", height=80, help="Information injected into the agent's memory when they pick this item up.")
                loc_options = all_loc_ids + [a.agent_id for a in sim.agents]
                cur_loc = item_data.get("location", all_loc_ids[0])
                loc_index = loc_options.index(cur_loc) if cur_loc in loc_options else 0
                new_item_loc = st.selectbox("Location", options=loc_options, index=loc_index, key=f"item_loc_{item_id}")
                if st.button("Apply", key=f"item_apply_{item_id}"):
                    item_data["name"] = new_item_name
                    item_data["description"] = new_item_desc
                    item_data["portable"] = new_item_portable
                    item_data["contested"] = new_item_contested
                    item_data["hidden"] = new_item_hidden
                    item_data["knowledge"] = new_item_knowledge
                    item_data["location"] = new_item_loc
                    st.success("Item updated.")


if __name__ == "__main__":
    main()
