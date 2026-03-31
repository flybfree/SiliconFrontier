#!/usr/bin/env python3
"""
Silicon Frontier - Streamlit Dashboard

Real-time monitoring interface for observing agent behavior, thoughts, and relationships.
Provides a "God Console" for experimental intervention.
"""

import sys
import json
import time
import os
from pathlib import Path
from datetime import datetime

import streamlit as st
from openai import OpenAI

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from app_paths import data_path, ensure_runtime_dirs
import scenario_editor

ensure_runtime_dirs()
os.chdir(data_path())


# ---------------------------------------------------------------------------
# Logging / tee
# ---------------------------------------------------------------------------

class _Tee:
    """Mirror all writes to both the original stream and a log file."""

    def __init__(self, stream, log_path: Path):
        self._stream = stream
        self._file = open(log_path, "w", encoding="utf-8")
        self.log_path = log_path

    def write(self, data):
        self._stream.write(data)
        self._file.write(data)

    def flush(self):
        self._stream.flush()
        self._file.flush()

    def close(self):
        self._file.close()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _start_logging(scenario: str) -> _Tee:
    log_dir = data_path("logs")
    log_dir.mkdir(exist_ok=True)
    slug = Path(scenario).name.replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{timestamp}_{slug}.log"
    tee = _Tee(sys.stdout, log_path)
    sys.stdout = tee
    return tee


def _stop_logging(tee: _Tee) -> None:
    sys.stdout = tee._stream
    tee.close()

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
    load_item_library,
    save_item_library,
    load_relationship_presets,
    load_scenario_manifest,
    resolve_item_placements,
    resolve_relationship_presets,
)

SYSTEM_STATUSES = ["ONLINE", "OFFLINE", "DEGRADED", "BROKEN"]


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
        self.config_dir = "scenarios/default"
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
                    if not self.world_state.add_item_to_agent_inventory(agent.agent_id, item_id):
                        import streamlit as st
                        st.warning(f"Item '{item_id}' in {agent.name}'s starting inventory does not exist in world_state.json — skipped.")
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

        # Load and resolve world state
        with open(Path(config_dir) / "world_state.json", "r", encoding="utf-8") as f:
            world_data = json.load(f)
        resolve_item_placements(world_data, load_item_library())
        self.agent_definitions, self.simulation_slots = load_agent_configuration(config_dir)
        resolve_relationship_presets(self.simulation_slots, world_data, load_relationship_presets())
        self.world_state = WorldState(world_data)

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
            with open(source_save, "r", encoding="utf-8") as f:
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
        save_path = data_path(save_dir)
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
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return filepath

    def load(self, filepath: str | Path) -> None:
        """Restore simulation state from a saved JSON file."""
        import copy

        with open(filepath, "r", encoding="utf-8") as f:
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
        p = data_path(save_dir)
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

    with st.expander(f"🤖 {agent.name} — {agent.emotional_state} @ {loc or 'unplaced'}"):
        loc_data = sim.world_state.get_location(loc)
        loc_name = loc_data.get("name", loc) if loc_data else (loc or "unknown")
        st.caption(f"ID: {agent.agent_id} | Archetype: {archetype_label} | Location: {loc_name} | Inventory: {inventory_str}")
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
        all_loc_ids = list(sim.world_state.locations.keys())
        cur_loc = sim.world_state.get_agent_location(agent.agent_id)
        loc_index = all_loc_ids.index(cur_loc) if cur_loc in all_loc_ids else 0
        new_loc = st.selectbox("Location", options=all_loc_ids, index=loc_index, key=f"loc_{agent.agent_id}")
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
            if not sim.world_state.set_agent_location(agent.agent_id, new_loc):
                sim.world_state.register_agent(agent.agent_id, new_loc)
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
            st.rerun()


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

    def _get_label(row_id: str, col_id: str) -> str:
        rel = relationships.get(row_id, {}).get(col_id, {})
        trust = int(rel.get("trust", 50))
        affinity = int(rel.get("affinity", 50))
        suspicion = sim.orchestrator.social.get_suspicion(row_id, col_id)
        return FrontierAgent._relationship_label(trust, affinity, suspicion)

    def _build_matrix(field: str, with_label: bool = True) -> "pd.DataFrame":
        rows = {}
        for row_agent in agents:
            row = {}
            row_data = relationships.get(row_agent.agent_id, {})
            for col_agent in agents:
                if row_agent.agent_id == col_agent.agent_id:
                    row[col_agent.name] = None
                else:
                    rel = row_data.get(col_agent.agent_id, {})
                    num = int(rel.get(field, 50))
                    if with_label:
                        label = _get_label(row_agent.agent_id, col_agent.agent_id)
                        row[col_agent.name] = f"{label} ({num})"
                    else:
                        row[col_agent.name] = num
            rows[row_agent.name] = row
        df = pd.DataFrame(rows).T
        df.index.name = "Observer ↓  /  Target →"
        return df

    def _extract_num(val) -> int | None:
        """Pull the numeric score out of a 'label (n)' string or raw int."""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        if isinstance(val, str):
            try:
                return int(val[val.rfind("(") + 1:val.rfind(")")])
            except (ValueError, AttributeError):
                return None
        return int(val)

    def _color_cell(val, high_bg: str, low_bg: str, mid_bg: str) -> str:
        num = _extract_num(val)
        if num is None:
            return "color: #555555"
        if num >= 70:
            return f"background-color: {high_bg}; color: white"
        if num <= 30:
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
        ).format(lambda v: "—" if v is None or (isinstance(v, float) and pd.isna(v)) else v)
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
        ).format(lambda v: "—" if v is None or (isinstance(v, float) and pd.isna(v)) else v)
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


def render_comms_log():
    """Render a filtered log of all inter-agent communications."""
    st.header("💬 Communications Log")

    comms = [
        e for e in sim.results_history
        if e.get("action") in {"SAY", "WHISPER", "LIE"} and e.get("success")
    ]

    if not comms:
        st.info("No communications yet.")
        return

    action_labels = {"SAY": "📢 SAY", "WHISPER": "🤫 WHISPER", "LIE": "🎭 LIE"}

    for entry in reversed(comms[-50:]):
        action = entry.get("action", "")
        agent = entry.get("agent_name", "?")
        cycle = entry.get("cycle", "?")
        raw_target = entry.get("target", "")

        if action == "WHISPER" and "->" in raw_target:
            message, recipient = raw_target.split("->", 1)
            label = f"Cycle {cycle} · {action_labels[action]} · **{agent}** → **{recipient.strip()}**: {message.strip()}"
        else:
            label = f"Cycle {cycle} · {action_labels[action]} · **{agent}**: {raw_target}"

        with st.expander(label):
            st.caption(f"Internal monologue: {entry.get('monologue', '')[:300]}...")


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
    with st.sidebar:
        app_mode = st.radio(
            "Workspace",
            options=["Simulation", "Scenario Editor"],
            key="app_workspace_mode",
        )

    if app_mode == "Scenario Editor":
        scenario_editor.main(embedded=True)
        return

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
        scenarios_root = data_path("scenarios")
        scenario_dirs = sorted([
            str(p.relative_to(data_path())).replace("\\", "/")
            for p in scenarios_root.iterdir()
            if p.is_dir() and (p / "world_state.json").exists()
        ]) if scenarios_root.exists() else []
        if not scenario_dirs:
            scenario_dirs = ["scenarios/default"]
        current_dir = sim.config_dir if sim.config_dir in scenario_dirs else scenario_dirs[0]

        def _scenario_label(path: str) -> str:
            manifest = load_scenario_manifest(path)
            name = manifest.get("name")
            count = manifest.get("agent_count")
            tags = manifest.get("tags", [])
            tag_str = f"  [{', '.join(tags)}]" if tags else ""
            count_str = f"  ({count} agents)" if count else ""
            return f"{name}{count_str}{tag_str}" if name else path

        config_dir = st.selectbox(
            "Scenario",
            options=scenario_dirs,
            index=scenario_dirs.index(current_dir),
            format_func=_scenario_label,
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

        enable_logging = st.checkbox(
            "Log to file",
            value=st.session_state.get("enable_logging", True),
            key="enable_logging",
            help="Mirror all simulation output to a timestamped file in logs/",
        )
        active_tee: _Tee | None = st.session_state.get("log_tee")
        if active_tee:
            st.caption(f"📄 Logging → `{active_tee.log_path.name}`")

        if st.button("🚀 Initialize Simulation"):
            # Stop any existing log before reinitialising
            if active_tee:
                _stop_logging(active_tee)
                st.session_state.log_tee = None
            if sim.initialize(config_dir=config_dir, llm_url=llm_url, llm_model=llm_model):
                st.session_state.initialized = True
                if enable_logging:
                    st.session_state.log_tee = _start_logging(config_dir)
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

    # Communications log
    render_comms_log()

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
                inline_tool_ids = list(sim.world_state.items.keys())
                library_tool_ids = list(load_item_library().get("items", {}).keys())
                tool_options = [""]
                for item_id in inline_tool_ids + library_tool_ids:
                    if item_id not in tool_options:
                        tool_options.append(item_id)

                def _tool_label(item_id: str) -> str:
                    if not item_id:
                        return "None"
                    world_item = sim.world_state.items.get(item_id, {})
                    lib_item = load_item_library().get("items", {}).get(item_id, {})
                    item_name = world_item.get("name") or lib_item.get("name") or item_id
                    return f"{item_name} ({item_id})"

                updated_systems = {}
                sys_to_delete = None
                if systems:
                    for system_id, system_data in systems.items():
                        st.markdown(f"`{system_id}`")
                        sc1, sc2, sc3 = st.columns([2, 2, 1])
                        with sc1:
                            sys_name = st.text_input(
                                "System Name",
                                value=system_data.get("name", system_id),
                                key=f"loc_sys_name_{loc_id}_{system_id}"
                            )
                        with sc2:
                            current_status = system_data.get("status", "ONLINE")
                            sys_status = st.selectbox(
                                "System Status",
                                options=SYSTEM_STATUSES,
                                index=SYSTEM_STATUSES.index(current_status) if current_status in SYSTEM_STATUSES else 0,
                                key=f"loc_sys_status_{loc_id}_{system_id}"
                            )
                        with sc3:
                            st.write("")
                            st.write("")
                            if st.button("Delete System", key=f"loc_sys_del_{loc_id}_{system_id}"):
                                sys_to_delete = system_id
                        sys_desc = st.text_input(
                            "System Description",
                            value=system_data.get("description", ""),
                            key=f"loc_sys_desc_{loc_id}_{system_id}"
                        )
                        current_repair_tool = system_data.get("required_tool_repair", system_data.get("required_tool", ""))
                        current_sabotage_tool = system_data.get("required_tool_sabotage", "")
                        tc1, tc2 = st.columns(2)
                        with tc1:
                            repair_tool = st.selectbox(
                                "Repair Tool",
                                options=tool_options,
                                index=tool_options.index(current_repair_tool) if current_repair_tool in tool_options else 0,
                                format_func=_tool_label,
                                key=f"loc_sys_repair_tool_{loc_id}_{system_id}"
                            )
                        with tc2:
                            sabotage_tool = st.selectbox(
                                "Sabotage Tool",
                                options=tool_options,
                                index=tool_options.index(current_sabotage_tool) if current_sabotage_tool in tool_options else 0,
                                format_func=_tool_label,
                                key=f"loc_sys_sabotage_tool_{loc_id}_{system_id}"
                            )
                        next_system = {
                            "name": sys_name,
                            "status": sys_status,
                            "description": sys_desc,
                        }
                        if repair_tool:
                            next_system["required_tool_repair"] = repair_tool
                        if sabotage_tool:
                            next_system["required_tool_sabotage"] = sabotage_tool
                        updated_systems[system_id] = next_system
                else:
                    st.caption("No systems configured.")

                with st.form(f"loc_add_system_{loc_id}"):
                    ac1, ac2, ac3 = st.columns([2, 2, 2])
                    with ac1:
                        add_sys_id = st.text_input("New System ID", key=f"loc_add_sys_id_{loc_id}")
                    with ac2:
                        add_sys_name = st.text_input("New System Name", key=f"loc_add_sys_name_{loc_id}")
                    with ac3:
                        add_sys_status = st.selectbox("New System Status", options=SYSTEM_STATUSES, key=f"loc_add_sys_status_{loc_id}")
                    add_sys_desc = st.text_input("New System Description", key=f"loc_add_sys_desc_{loc_id}")
                    at1, at2 = st.columns(2)
                    with at1:
                        add_sys_repair_tool = st.selectbox(
                            "New Repair Tool",
                            options=tool_options,
                            format_func=_tool_label,
                            key=f"loc_add_sys_repair_tool_{loc_id}"
                        )
                    with at2:
                        add_sys_sabotage_tool = st.selectbox(
                            "New Sabotage Tool",
                            options=tool_options,
                            format_func=_tool_label,
                            key=f"loc_add_sys_sabotage_tool_{loc_id}"
                        )
                    add_system_submitted = st.form_submit_button("Add System")
                if sys_to_delete and sys_to_delete in updated_systems:
                    del updated_systems[sys_to_delete]
                    loc_data["systems"] = updated_systems
                    st.success("System deleted.")
                    st.rerun()
                if add_system_submitted:
                    if not add_sys_id.strip() or not add_sys_name.strip():
                        st.error("New system ID and name are required.")
                    elif add_sys_id.strip() in updated_systems:
                        st.error(f"System ID '{add_sys_id.strip()}' already exists in this location.")
                    else:
                        new_system = {
                            "name": add_sys_name.strip(),
                            "status": add_sys_status,
                            "description": add_sys_desc.strip(),
                        }
                        if add_sys_repair_tool:
                            new_system["required_tool_repair"] = add_sys_repair_tool
                        if add_sys_sabotage_tool:
                            new_system["required_tool_sabotage"] = add_sys_sabotage_tool
                        updated_systems[add_sys_id.strip()] = new_system
                        loc_data["systems"] = updated_systems
                        st.success("System added.")
                        st.rerun()
                if st.button("Apply", key=f"loc_apply_{loc_id}"):
                    loc_data["name"] = new_name
                    loc_data["description"] = new_desc
                    loc_data["connected_to"] = [s.strip() for s in new_connected.split(",") if s.strip()]
                    loc_data["status_effects"] = [s.strip() for s in new_effects.split(",") if s.strip()]
                    loc_data["systems"] = updated_systems
                    st.success("Location updated.")

    with item_tab:
        EMOTIONAL_STATES = [
            "", "Calm", "Alert", "Anxious", "Fearful", "Angry", "Hopeful",
            "Suspicious", "Confident", "Resigned", "Determined", "Neutral",
        ]

        all_loc_ids = list(sim.world_state.locations.keys())
        with st.expander("➕ Add New Item"):
            add_custom_tab, add_library_tab = st.tabs(["Custom Item", "From Library"])

            with add_custom_tab:
                ni_id = st.text_input("Item ID (e.g. soda_can)", key="new_item_id")
                ni_name = st.text_input("Name", key="new_item_name")
                ni_desc = st.text_area("Description", key="new_item_desc", height=80)
                ni_loc = st.selectbox("Starting Location", options=all_loc_ids, key="new_item_loc")
                _c1, _c2, _c3, _c4 = st.columns(4)
                ni_portable  = _c1.checkbox("Portable",   value=True, key="new_item_portable")
                ni_contested = _c2.checkbox("Contested",              key="new_item_contested")
                ni_hidden    = _c3.checkbox("Hidden",                 key="new_item_hidden")
                ni_consumable= _c4.checkbox("Consumable",             key="new_item_consumable")
                if ni_hidden:
                    ni_knowledge = st.text_area("Knowledge (revealed on pickup)", key="new_item_knowledge", height=60)
                else:
                    ni_knowledge = ""
                ni_effect = {}
                if ni_consumable:
                    st.markdown("**Effect fields**")
                    _e1, _e2 = st.columns(2)
                    with _e1:
                        ni_perc_delta = st.number_input("Perception delta", step=1, value=0, key="new_item_perc_delta")
                        ni_emo = st.selectbox("Emotional state override", options=EMOTIONAL_STATES, key="new_item_emo")
                    with _e2:
                        ni_mem = st.text_area("Memory inject", height=80, key="new_item_mem")
                    if ni_perc_delta:
                        ni_effect["perception_delta"] = int(ni_perc_delta)
                    if ni_emo:
                        ni_effect["emotional_state"] = ni_emo
                    if ni_mem.strip():
                        ni_effect["memory_inject"] = ni_mem.strip()

                if st.button("Create Item", key="create_item"):
                    if not ni_id.strip():
                        st.error("Item ID is required.")
                    elif ni_id.strip() in sim.world_state.items:
                        st.error(f"ID '{ni_id.strip()}' already exists.")
                    else:
                        sim.world_state.add_item(
                            item_id=ni_id.strip(),
                            name=ni_name.strip() or ni_id.strip(),
                            location=ni_loc,
                            description=ni_desc.strip(),
                            portable=ni_portable,
                        )
                        entry = sim.world_state.items[ni_id.strip()]
                        if ni_contested:
                            entry["contested"] = True
                        if ni_hidden:
                            entry["hidden"] = True
                            entry["knowledge"] = ni_knowledge.strip()
                        if ni_consumable:
                            entry["consumable"] = True
                            if ni_effect:
                                entry["effect"] = ni_effect
                        st.success(f"Item '{ni_id.strip()}' created.")
                        st.rerun()

            with add_library_tab:
                item_library = load_item_library()
                lib_items = item_library.get("items", {})
                existing_ids = set(sim.world_state.items.keys())
                available_lib = {iid: idata for iid, idata in lib_items.items() if iid not in existing_ids}

                if not available_lib:
                    st.info("All library items are already in the world.")
                else:
                    lib_options = list(available_lib.keys())
                    lib_sel = st.selectbox(
                        "Library item",
                        options=lib_options,
                        format_func=lambda x: f"{available_lib[x].get('name', x)} ({x})",
                        key="lib_item_sel",
                    )
                    sel = available_lib[lib_sel]
                    st.caption(sel.get("description", ""))
                    flags = []
                    if sel.get("contested"): flags.append("contested")
                    if sel.get("hidden"):    flags.append("hidden")
                    if sel.get("consumable"):flags.append("consumable")
                    if flags:
                        st.caption(f"Flags: {', '.join(flags)}")
                    if sel.get("knowledge"):
                        st.caption(f"Knowledge: *{sel['knowledge'][:120]}{'…' if len(sel.get('knowledge','')) > 120 else ''}*")
                    if sel.get("effect"):
                        st.caption(f"Effect: {sel['effect']}")

                    lib_loc = st.selectbox("Place in location", options=all_loc_ids,
                                           format_func=lambda x: sim.world_state.locations.get(x, {}).get("name", x),
                                           key="lib_item_loc")
                    lib_contested_override = st.checkbox("Contested override", value=sel.get("contested", False), key="lib_item_contested")

                    if st.button("Place Item", key="place_lib_item"):
                        import copy as _copy
                        new_entry = _copy.deepcopy(sel)
                        new_entry["location"] = lib_loc
                        new_entry.setdefault("owner", None)
                        new_entry["contested"] = lib_contested_override
                        sim.world_state.items[lib_sel] = new_entry
                        st.success(f"Placed '{sel.get('name', lib_sel)}' in {lib_loc}.")
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
                _col_port, _col_cont, _col_hid, _col_cons = st.columns(4)
                new_item_portable   = _col_port.checkbox("Portable",   value=item_data.get("portable", True),   key=f"item_port_{item_id}")
                new_item_contested  = _col_cont.checkbox("Contested",  value=item_data.get("contested", False),  key=f"item_contested_{item_id}")
                new_item_hidden     = _col_hid.checkbox("Hidden",      value=item_data.get("hidden", False),     key=f"item_hidden_{item_id}")
                new_item_consumable = _col_cons.checkbox("Consumable", value=item_data.get("consumable", False), key=f"item_consumable_{item_id}")
                if new_item_hidden:
                    new_item_knowledge = st.text_area("Knowledge (revealed on pickup)", value=item_data.get("knowledge", ""), key=f"item_knowledge_{item_id}", height=80)
                else:
                    new_item_knowledge = ""
                new_effect = {}
                if new_item_consumable:
                    st.markdown("**Effect fields**")
                    existing_effect = item_data.get("effect", {})
                    _e1, _e2 = st.columns(2)
                    with _e1:
                        new_perc_delta = st.number_input("Perception delta", step=1, value=int(existing_effect.get("perception_delta", 0)), key=f"item_perc_{item_id}")
                        cur_emo = existing_effect.get("emotional_state", "")
                        emo_opts = EMOTIONAL_STATES
                        new_emo = st.selectbox("Emotional state override", options=emo_opts, index=emo_opts.index(cur_emo) if cur_emo in emo_opts else 0, key=f"item_emo_{item_id}")
                    with _e2:
                        new_mem = st.text_area("Memory inject", value=existing_effect.get("memory_inject", ""), height=80, key=f"item_mem_{item_id}")
                    if new_perc_delta:
                        new_effect["perception_delta"] = int(new_perc_delta)
                    if new_emo:
                        new_effect["emotional_state"] = new_emo
                    if new_mem.strip():
                        new_effect["memory_inject"] = new_mem.strip()
                loc_options = all_loc_ids + [a.agent_id for a in sim.agents]
                cur_loc = item_data.get("location", all_loc_ids[0] if all_loc_ids else "")
                loc_index = loc_options.index(cur_loc) if cur_loc in loc_options else 0
                new_item_loc = st.selectbox("Location", options=loc_options, index=loc_index, key=f"item_loc_{item_id}")
                _btn_apply, _btn_lib, _ = st.columns([1, 1, 4])
                with _btn_apply:
                    if st.button("Apply", key=f"item_apply_{item_id}"):
                        item_data["name"] = new_item_name
                        item_data["description"] = new_item_desc
                        item_data["portable"] = new_item_portable
                        item_data["contested"] = new_item_contested
                        item_data["hidden"] = new_item_hidden
                        item_data["knowledge"] = new_item_knowledge if new_item_hidden else ""
                        item_data["consumable"] = new_item_consumable
                        if new_item_consumable and new_effect:
                            item_data["effect"] = new_effect
                        elif "effect" in item_data and not new_item_consumable:
                            del item_data["effect"]
                        item_data["location"] = new_item_loc
                        st.success("Item updated.")
                with _btn_lib:
                    item_lib = load_item_library()
                    in_lib = item_id in item_lib.get("items", {})
                    if st.button("Update Library" if in_lib else "Save to Library", key=f"item_to_lib_{item_id}"):
                        lib_entry = {
                            "name": new_item_name,
                            "description": new_item_desc,
                            "portable": new_item_portable,
                        }
                        if new_item_contested:
                            lib_entry["contested"] = True
                        if new_item_hidden and new_item_knowledge.strip():
                            lib_entry["hidden"] = True
                            lib_entry["knowledge"] = new_item_knowledge.strip()
                        if new_item_consumable:
                            lib_entry["consumable"] = True
                            if new_effect:
                                lib_entry["effect"] = new_effect
                        item_lib["items"][item_id] = lib_entry
                        save_item_library(item_lib)
                        st.success(f"{'Updated' if in_lib else 'Saved'} '{item_id}' in library.")


if __name__ == "__main__":
    main()
