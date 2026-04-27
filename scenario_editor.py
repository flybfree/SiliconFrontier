#!/usr/bin/env python3
"""
Silicon Frontier - Scenario Editor

A form-based UI for creating and editing scenario assets without hand-editing JSON.
Run with: streamlit run scenario_editor.py
"""

import copy
import json
import sys
import os
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from app_paths import data_path, ensure_runtime_dirs

ensure_runtime_dirs()
os.chdir(data_path())

from configloader import (
    load_scenario_manifest,
    load_item_library,
    save_item_library,
    load_agent_library,
    save_agent_library,
    load_relationship_presets,
    load_agent_configuration,
    save_agent_definitions,
    save_simulation_slots,
    save_world_state,
    AGENT_DEFINITIONS_FILENAME,
    SIMULATION_AGENTS_FILENAME,
)

def configure_page() -> None:
    st.set_page_config(
        page_title="SF Scenario Editor",
        page_icon="🛠",
        layout="wide",
    )

st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    div[data-testid="stExpander"] { border: 1px solid #333; border-radius: 4px; margin-bottom: 6px; }
    .dirty-badge { color: #f0a500; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Emotional state options for consumable effects
# ---------------------------------------------------------------------------

EMOTIONAL_STATES = [
    "", "Calm", "Alert", "Anxious", "Fearful", "Angry", "Hopeful",
    "Suspicious", "Confident", "Resigned", "Determined", "Neutral",
]

SYSTEM_STATUSES = ["ONLINE", "OFFLINE", "DEGRADED", "BROKEN"]

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

def _init_session() -> None:
    st.session_state.se_initialized = True
    st.session_state.se_scenario_dir = None
    st.session_state.se_scenario_manifest = {}
    st.session_state.se_agent_definitions = {"agents": []}
    st.session_state.se_simulation_slots = {"slots": [], "relationships": []}
    st.session_state.se_world_state = {
        "locations": {}, "items": {}, "item_placements": [],
        "agents": {}, "relationships": {},
    }
    st.session_state.se_item_library = load_item_library()
    st.session_state.se_agent_library = load_agent_library()
    st.session_state.se_relationship_presets = load_relationship_presets()
    st.session_state.se_dirty = False
    st.session_state.se_confirm_load = False


if "se_initialized" not in st.session_state:
    _init_session()

# ---------------------------------------------------------------------------
# Convenience aliases
# ---------------------------------------------------------------------------

def _ss():
    return st.session_state

def _world() -> dict:
    return st.session_state.se_world_state

def _defs() -> dict:
    return st.session_state.se_agent_definitions

def _slots() -> dict:
    return st.session_state.se_simulation_slots

def _library() -> dict:
    if "se_item_library" not in st.session_state:
        st.session_state.se_item_library = load_item_library()
    return st.session_state.se_item_library

def _presets() -> dict:
    return st.session_state.se_relationship_presets

def _mark_dirty() -> None:
    st.session_state.se_dirty = True

# ---------------------------------------------------------------------------
# Derived helpers (always read live from session state)
# ---------------------------------------------------------------------------

def _location_options() -> list[str]:
    return list(_world().get("locations", {}).keys())

def _location_name(loc_id: str) -> str:
    return _world().get("locations", {}).get(loc_id, {}).get("name", loc_id)

def _definition_map() -> dict[str, dict]:
    return {a["definition_id"]: a for a in _defs().get("agents", [])}

def _definition_options() -> list[str]:
    return [a["definition_id"] for a in _defs().get("agents", [])]

def _definition_name(def_id: str) -> str:
    return _definition_map().get(def_id, {}).get("name", def_id)

def _active_slot_def_ids() -> list[str]:
    return [s["definition_id"] for s in _slots().get("slots", [])]

def _all_item_ids() -> list[str]:
    inline = list(_world().get("items", {}).keys())
    placed = [p["item_id"] for p in _world().get("item_placements", [])]
    seen = set()
    result = []
    for iid in inline + placed:
        if iid not in seen:
            seen.add(iid)
            result.append(iid)
    return result

def _item_display_name(item_id: str) -> str:
    inline = _world().get("items", {}).get(item_id, {})
    if inline.get("name"):
        return inline["name"]
    lib = _library().get("items", {}).get(item_id, {})
    if lib.get("name"):
        return lib["name"]
    return item_id

def _tool_options() -> list[str]:
    """Return selectable tool/item IDs for system requirements."""
    options = [""]
    seen = {""}
    for item_id in _all_item_ids():
        if item_id not in seen:
            seen.add(item_id)
            options.append(item_id)
    for item_id in _library().get("items", {}).keys():
        if item_id not in seen:
            seen.add(item_id)
            options.append(item_id)
    return options

def _tool_label(item_id: str) -> str:
    """Return a friendly label for a tool dropdown option."""
    if not item_id:
        return "None"
    return f"{_item_display_name(item_id)} ({item_id})"

def _preset_names() -> list[str]:
    return list(_presets().get("presets", {}).keys())

def _agent_library() -> dict:
    if "se_agent_library" not in st.session_state:
        st.session_state.se_agent_library = load_agent_library()
    return st.session_state.se_agent_library

def _slugify(name: str) -> str:
    return name.lower().strip().replace(" ", "_").replace("-", "_")

# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def _load_scenario(path_str: str) -> None:
    path = Path(path_str)
    if not path.exists():
        st.error(f"Directory not found: {path}")
        return

    try:
        agent_defs, sim_slots = load_agent_configuration(str(path))
        world_path = path / "world_state.json"
        world_data = json.loads(world_path.read_text(encoding="utf-8")) if world_path.exists() else {
            "locations": {}, "items": {}, "item_placements": [],
            "agents": {}, "relationships": {},
        }
        manifest = load_scenario_manifest(str(path))
    except Exception as exc:
        st.error(f"Failed to load scenario: {exc}")
        return

    st.session_state.se_scenario_dir = str(path)
    st.session_state.se_scenario_manifest = manifest
    st.session_state.se_agent_definitions = copy.deepcopy(agent_defs)
    st.session_state.se_simulation_slots = copy.deepcopy(sim_slots)
    st.session_state.se_world_state = copy.deepcopy(world_data)
    st.session_state.se_dirty = False
    st.session_state.se_confirm_load = False


def _create_new_scenario(name: str) -> None:
    slug = _slugify(name)
    path = data_path("scenarios") / slug
    if path.exists():
        st.error(f"Scenario directory already exists: {path}")
        return
    path.mkdir(parents=True)

    manifest = {"name": name, "description": "", "agent_count": 0, "tags": [], "notes": ""}
    agent_defs = {"agents": []}
    sim_slots = {"slots": [], "relationships": []}
    world_data = {"locations": {}, "items": {}, "item_placements": [], "agents": {}, "relationships": {}}

    (path / "scenario.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (path / AGENT_DEFINITIONS_FILENAME).write_text(json.dumps(agent_defs, indent=2), encoding="utf-8")
    (path / SIMULATION_AGENTS_FILENAME).write_text(json.dumps(sim_slots, indent=2), encoding="utf-8")
    (path / "world_state.json").write_text(json.dumps(world_data, indent=2), encoding="utf-8")

    st.session_state.se_scenario_dir = str(path)
    st.session_state.se_scenario_manifest = manifest
    st.session_state.se_agent_definitions = agent_defs
    st.session_state.se_simulation_slots = sim_slots
    st.session_state.se_world_state = world_data
    st.session_state.se_dirty = False


def _save_all() -> None:
    path = _ss().se_scenario_dir
    if not path:
        st.error("No scenario loaded.")
        return
    try:
        # Auto-derive agent_count
        manifest = copy.deepcopy(_ss().se_scenario_manifest)
        manifest["agent_count"] = len(_slots().get("slots", []))
        save_world_state(_world(), path)
        save_agent_definitions(_defs(), path)
        save_simulation_slots(_slots(), path)
        (Path(path) / "scenario.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        st.session_state.se_scenario_manifest = manifest
        st.session_state.se_dirty = False
        st.success("Saved.")
    except Exception as exc:
        st.error(f"Save failed: {exc}")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.header("Scenario Manager")

        loaded = _ss().se_scenario_dir
        if loaded:
            dirty = _ss().se_dirty
            label = Path(loaded).name
            badge = " ●" if dirty else " ✓"
            st.caption(f"Loaded: **{label}**{badge}")
        else:
            st.caption("No scenario loaded.")

        st.divider()

        # --- Load existing ---
        st.subheader("Load Existing")
        scenarios_root = data_path("scenarios")
        available = sorted(
            [str(p.relative_to(data_path())).replace("\\", "/") for p in scenarios_root.iterdir() if p.is_dir()]
            if scenarios_root.exists() else []
        )
        input_dir = st.text_input(
            "Scenario path", value=available[0] if available else "scenarios/default",
            key="se_input_dir",
        )
        if available:
            st.selectbox(
                "Or pick from list", options=["— type above —"] + available,
                key="se_pick_dir",
                on_change=lambda: st.session_state.update(se_input_dir=st.session_state.se_pick_dir)
                if st.session_state.se_pick_dir != "— type above —" else None,
            )

        if st.button("Load Scenario", use_container_width=True):
            if _ss().se_dirty and not _ss().se_confirm_load:
                st.session_state.se_confirm_load = True
                st.rerun()
            else:
                _load_scenario(st.session_state.se_input_dir)
                st.rerun()

        if _ss().se_confirm_load:
            st.warning("You have unsaved changes.")
            if st.button("Load anyway (discard changes)", use_container_width=True):
                _load_scenario(st.session_state.se_input_dir)
                st.rerun()
            if st.button("Cancel", use_container_width=True):
                st.session_state.se_confirm_load = False
                st.rerun()

        st.divider()

        # --- Create new ---
        st.subheader("Create New")
        new_name = st.text_input("Scenario name", key="se_new_name")
        if st.button("Create", use_container_width=True, disabled=not new_name.strip()):
            _create_new_scenario(new_name.strip())
            st.rerun()

        st.divider()

        # --- Save ---
        if st.button(
            "💾 Save All",
            use_container_width=True,
            type="primary",
            disabled=not _ss().se_dirty or not _ss().se_scenario_dir,
        ):
            _save_all()
            st.rerun()

        if _ss().se_scenario_dir and _ss().se_dirty:
            st.warning("Unsaved changes.")

# ---------------------------------------------------------------------------
# Tab 1 — Scenario metadata
# ---------------------------------------------------------------------------

def render_tab_scenario() -> None:
    if not _ss().se_scenario_dir:
        st.info("Load or create a scenario to begin.")
        return

    manifest = _ss().se_scenario_manifest

    def _update(key: str, value) -> None:
        _ss().se_scenario_manifest[key] = value
        _mark_dirty()

    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name", value=manifest.get("name", ""), key="se_meta_name")
        if name != manifest.get("name", ""):
            _update("name", name)

        rounds = st.number_input(
            "Recommended rounds", min_value=1, step=1,
            value=int(manifest.get("recommended_rounds", 10)),
            key="se_meta_rounds",
        )
        if rounds != manifest.get("recommended_rounds"):
            _update("recommended_rounds", int(rounds))

    with col2:
        tags_str = ", ".join(manifest.get("tags", []))
        new_tags = st.text_input("Tags (comma-separated)", value=tags_str, key="se_meta_tags")
        parsed_tags = [t.strip() for t in new_tags.split(",") if t.strip()]
        if parsed_tags != manifest.get("tags", []):
            _update("tags", parsed_tags)

    desc = st.text_area("Description", value=manifest.get("description", ""), height=80, key="se_meta_desc")
    if desc != manifest.get("description", ""):
        _update("description", desc)

    notes = st.text_area("Notes", value=manifest.get("notes", ""), height=80, key="se_meta_notes")
    if notes != manifest.get("notes", ""):
        _update("notes", notes)

    st.caption(f"Scenario directory: `{_ss().se_scenario_dir}`")
    slot_count = len(_slots().get("slots", []))
    st.caption(f"Agent count (auto from slots): **{slot_count}**")

# ---------------------------------------------------------------------------
# Tab 2 — Agent definitions
# ---------------------------------------------------------------------------

DEFAULT_AGENT_CONDITION = {
    "health": 100,
    "stress": 0,
    "fatigue": 0,
    "morale": 50
}


def _agent_condition(defaults: dict) -> dict:
    condition = dict(DEFAULT_AGENT_CONDITION)
    raw = defaults.get("condition", {})
    if isinstance(raw, dict):
        for key in condition:
            condition[key] = max(0, min(100, int(raw.get(key, condition[key]))))
    return condition


def _agent_fields(key_prefix: str, defaults: dict) -> dict:
    """Render the common agent fields and return a dict of current widget values."""
    condition = _agent_condition(defaults)
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name", value=defaults.get("name", ""), key=f"{key_prefix}_name")
        role = st.text_input("Role", value=defaults.get("role", ""), key=f"{key_prefix}_role")
        arch = st.selectbox(
            "Archetype", ["standard", "saboteur"],
            index=0 if defaults.get("archetype", "standard") == "standard" else 1,
            key=f"{key_prefix}_arch",
        )
        perc = st.slider("Perception", 0, 100, value=int(defaults.get("perception", 50)), key=f"{key_prefix}_perc")
        health = st.slider("Health", 0, 100, value=condition["health"], key=f"{key_prefix}_health")
        stress = st.slider("Stress", 0, 100, value=condition["stress"], key=f"{key_prefix}_stress")
        fatigue = st.slider("Fatigue", 0, 100, value=condition["fatigue"], key=f"{key_prefix}_fatigue")
        morale = st.slider("Morale", 0, 100, value=condition["morale"], key=f"{key_prefix}_morale")
    with col2:
        persona = st.text_area("Persona", value=defaults.get("persona", ""), height=130, key=f"{key_prefix}_persona")
        secret = st.text_area("Secret Goal", value=defaults.get("secret_goal", ""), height=130, key=f"{key_prefix}_secret")
    return {"name": name, "role": role, "archetype": arch, "perception": perc,
            "condition": {"health": health, "stress": stress, "fatigue": fatigue, "morale": morale},
            "persona": persona, "secret_goal": secret}


def render_tab_agents() -> None:
    if not _ss().se_scenario_dir:
        st.info("Load or create a scenario first.")
        return

    scenario_agents = _defs().get("agents", [])
    lib_agents: dict = _agent_library().get("agents", {})
    scenario_ids = {a["definition_id"] for a in scenario_agents}

    scenario_tab, library_tab = st.tabs([
        f"In This Scenario ({len(scenario_agents)})",
        f"Agent Library ({len(lib_agents)})",
    ])

    # ---- Scenario agents ----
    with scenario_tab:
        st.caption("Agents defined in this scenario's agent_definitions.json.")

        for idx, agent in enumerate(scenario_agents):
            did = agent["definition_id"]
            in_lib = did in lib_agents
            lib_badge = " 📚" if in_lib else ""
            label = f"{agent['name']} — {agent['role']} [{agent['archetype']}]{lib_badge}"

            with st.expander(label, expanded=False):
                vals = _agent_fields(f"adef_{did}", agent)

                c_apply, c_save_lib, c_del, _ = st.columns([1, 1, 1, 3])
                with c_apply:
                    if st.button("Apply", key=f"adef_apply_{did}"):
                        scenario_agents[idx].update({
                            "name": vals["name"].strip(),
                            "role": vals["role"].strip(),
                            "archetype": vals["archetype"],
                            "perception": vals["perception"],
                            "condition": vals["condition"],
                            "persona": vals["persona"].strip(),
                            "secret_goal": vals["secret_goal"].strip(),
                        })
                        _mark_dirty()
                        st.rerun()
                with c_save_lib:
                    save_label = "Update Library" if in_lib else "Save to Library"
                    if st.button(save_label, key=f"adef_to_lib_{did}"):
                        lib = _agent_library()
                        lib["agents"][did] = {
                            "name": vals["name"].strip(),
                            "role": vals["role"].strip(),
                            "archetype": vals["archetype"],
                            "perception": vals["perception"],
                            "condition": vals["condition"],
                            "persona": vals["persona"].strip(),
                            "secret_goal": vals["secret_goal"].strip(),
                        }
                        save_agent_library(lib)
                        st.session_state.se_agent_library = lib
                        st.success(f"{'Updated' if in_lib else 'Saved'} '{did}' in library.")
                        st.rerun()
                with c_del:
                    if st.button("Remove", key=f"adef_del_{did}", type="secondary"):
                        referencing = [s["slot_id"] for s in _slots().get("slots", []) if s.get("definition_id") == did]
                        if referencing:
                            st.error(f"Cannot remove: used by slots {referencing}.")
                        else:
                            _defs()["agents"].pop(idx)
                            _mark_dirty()
                            st.rerun()

        st.divider()
        with st.expander("➕ Create New Agent", expanded=False):
            with st.form("form_add_agent"):
                f_id = st.text_input("Definition ID* (snake_case)", help="Unique key, e.g. dr_morales")
                vals = _agent_fields("form_new_agent", {})
                if st.form_submit_button("Add to Scenario"):
                    clean_id = f_id.strip() or _slugify(vals["name"])
                    if not clean_id or not vals["name"].strip() or not vals["role"].strip():
                        st.error("ID, Name, and Role are required.")
                    elif clean_id in scenario_ids:
                        st.error(f"Definition ID '{clean_id}' already exists in this scenario.")
                    else:
                        _defs()["agents"].append({
                            "definition_id": clean_id,
                            "name": vals["name"].strip(),
                            "role": vals["role"].strip(),
                            "archetype": vals["archetype"],
                            "perception": vals["perception"],
                            "condition": vals["condition"],
                            "persona": vals["persona"].strip(),
                            "secret_goal": vals["secret_goal"].strip(),
                        })
                        _mark_dirty()
                        st.rerun()

    # ---- Agent library ----
    with library_tab:
        st.caption("Reusable agent definitions from library/agents.json. Add them to the current scenario or edit the library entry directly.")

        for lib_id, lib_agent in lib_agents.items():
            already_in_scenario = lib_id in scenario_ids
            badge = " ✓ in scenario" if already_in_scenario else ""
            label = f"{lib_agent.get('name', lib_id)} — {lib_agent.get('role', '')} [{lib_agent.get('archetype', 'standard')}]{badge}"

            with st.expander(label, expanded=False):
                vals = _agent_fields(f"lib_{lib_id}", lib_agent)

                c_add, c_update, c_del, _ = st.columns([1, 1, 1, 3])
                with c_add:
                    btn_label = "Re-add to Scenario" if already_in_scenario else "Add to Scenario"
                    if st.button(btn_label, key=f"lib_add_{lib_id}", disabled=already_in_scenario):
                        _defs()["agents"].append({
                            "definition_id": lib_id,
                            "name": lib_agent.get("name", ""),
                            "role": lib_agent.get("role", ""),
                            "archetype": lib_agent.get("archetype", "standard"),
                            "perception": lib_agent.get("perception", 50),
                            "condition": _agent_condition(lib_agent),
                            "persona": lib_agent.get("persona", ""),
                            "secret_goal": lib_agent.get("secret_goal", ""),
                        })
                        _mark_dirty()
                        st.rerun()
                with c_update:
                    if st.button("Update Library", key=f"lib_update_{lib_id}"):
                        lib = _agent_library()
                        lib["agents"][lib_id] = {
                            "name": vals["name"].strip(),
                            "role": vals["role"].strip(),
                            "archetype": vals["archetype"],
                            "perception": vals["perception"],
                            "condition": vals["condition"],
                            "persona": vals["persona"].strip(),
                            "secret_goal": vals["secret_goal"].strip(),
                        }
                        save_agent_library(lib)
                        st.session_state.se_agent_library = lib
                        st.success(f"Library entry '{lib_id}' updated.")
                        st.rerun()
                with c_del:
                    if st.button("Delete from Library", key=f"lib_del_{lib_id}", type="secondary"):
                        lib = _agent_library()
                        del lib["agents"][lib_id]
                        save_agent_library(lib)
                        st.session_state.se_agent_library = lib
                        st.rerun()

        st.divider()
        with st.expander("➕ Add New Library Agent", expanded=False):
            with st.form("form_add_lib_agent"):
                f_lib_id = st.text_input("Definition ID* (snake_case)")
                vals = _agent_fields("form_new_lib_agent", {})
                if st.form_submit_button("Save to Library"):
                    clean_id = f_lib_id.strip() or _slugify(vals["name"])
                    if not clean_id or not vals["name"].strip() or not vals["role"].strip():
                        st.error("ID, Name, and Role are required.")
                    elif clean_id in lib_agents:
                        st.error(f"Library already contains '{clean_id}'.")
                    else:
                        lib = _agent_library()
                        lib["agents"][clean_id] = {
                            "name": vals["name"].strip(),
                            "role": vals["role"].strip(),
                            "archetype": vals["archetype"],
                            "perception": vals["perception"],
                            "condition": vals["condition"],
                            "persona": vals["persona"].strip(),
                            "secret_goal": vals["secret_goal"].strip(),
                        }
                        save_agent_library(lib)
                        st.session_state.se_agent_library = lib
                        st.rerun()

# ---------------------------------------------------------------------------
# Tab 3 — Simulation slots
# ---------------------------------------------------------------------------

def render_tab_slots() -> None:
    if not _ss().se_scenario_dir:
        st.info("Load or create a scenario first.")
        return

    slots = _slots().get("slots", [])
    def_options = _definition_options()
    loc_options = _location_options()
    all_items = _all_item_ids()

    st.caption(f"{len(slots)} active slot(s)")

    for idx, slot in enumerate(slots):
        sid = slot["slot_id"]
        label = f"{sid} → {_definition_name(slot.get('definition_id', ''))} @ {_location_name(slot.get('starting_location', ''))}"
        with st.expander(label, expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                def_idx = def_options.index(slot["definition_id"]) if slot.get("definition_id") in def_options else 0
                n_def = st.selectbox(
                    "Agent Definition",
                    options=def_options,
                    index=def_idx,
                    format_func=_definition_name,
                    key=f"slot_def_{sid}",
                )
                n_inst = st.text_input("Instance ID", value=slot.get("instance_id", sid), key=f"slot_inst_{sid}")
                loc_idx = loc_options.index(slot["starting_location"]) if slot.get("starting_location") in loc_options else 0
                n_loc = st.selectbox(
                    "Starting Location",
                    options=loc_options,
                    index=loc_idx,
                    format_func=_location_name,
                    key=f"slot_loc_{sid}",
                ) if loc_options else st.text_input("Starting Location", value=slot.get("starting_location", ""), key=f"slot_loc_txt_{sid}")
            with c2:
                n_inv = st.multiselect(
                    "Starting Inventory",
                    options=all_items,
                    default=[i for i in slot.get("inventory", []) if i in all_items],
                    format_func=_item_display_name,
                    key=f"slot_inv_{sid}",
                )

            c_apply, c_del, _ = st.columns([1, 1, 4])
            with c_apply:
                if st.button("Apply", key=f"slot_apply_{sid}"):
                    slots[idx].update({
                        "definition_id": n_def,
                        "instance_id": n_inst.strip() or n_def,
                        "starting_location": n_loc if loc_options else st.session_state.get(f"slot_loc_txt_{sid}", ""),
                        "inventory": n_inv,
                    })
                    _mark_dirty()
                    st.rerun()
            with c_del:
                if st.button("Delete", key=f"slot_del_{sid}", type="secondary"):
                    # Remove relationships involving this slot's instance_id
                    inst_id = slot.get("instance_id", sid)
                    def_id = slot.get("definition_id", "")
                    _slots()["relationships"] = [
                        r for r in _slots().get("relationships", [])
                        if r.get("from") not in (inst_id, def_id) and r.get("to") not in (inst_id, def_id)
                    ]
                    _slots()["slots"].pop(idx)
                    _mark_dirty()
                    st.rerun()

    st.divider()
    with st.expander("➕ Add Simulation Slot", expanded=False):
        if not def_options:
            st.info("Add agent definitions first.")
        elif not loc_options:
            st.info("Add locations first.")
        else:
            with st.form("form_add_slot"):
                f_def = st.selectbox("Agent Definition", options=def_options, format_func=_definition_name)
                f_loc = st.selectbox("Starting Location", options=loc_options, format_func=_location_name)
                f_inv = st.multiselect("Starting Inventory", options=all_items, format_func=_item_display_name)
                submitted = st.form_submit_button("Add Slot")
                if submitted:
                    new_n = len(slots) + 1
                    _slots()["slots"].append({
                        "slot_id": f"slot_{new_n}",
                        "instance_id": f_def,
                        "definition_id": f_def,
                        "starting_location": f_loc,
                        "inventory": f_inv,
                    })
                    _mark_dirty()
                    st.rerun()

# ---------------------------------------------------------------------------
# Tab 4 — Items
# ---------------------------------------------------------------------------

def _render_effect_fields(key_prefix: str, existing_effect: dict) -> dict:
    """Render consumable effect sub-fields; return the current dict of values."""
    st.markdown("**Effect fields**")
    c1, c2 = st.columns(2)
    with c1:
        perc_delta = st.number_input(
            "Perception delta", step=1,
            value=int(existing_effect.get("perception_delta", 0)),
            key=f"{key_prefix}_perc_delta",
            help="Positive sharpens, negative dulls. 0 = no change.",
        )
        health_delta = st.number_input("Health delta", step=1, value=int(existing_effect.get("health_delta", 0)), key=f"{key_prefix}_health_delta")
        stress_delta = st.number_input("Stress delta", step=1, value=int(existing_effect.get("stress_delta", 0)), key=f"{key_prefix}_stress_delta")
        emo_options = EMOTIONAL_STATES
        cur_emo = existing_effect.get("emotional_state", "")
        emo_idx = emo_options.index(cur_emo) if cur_emo in emo_options else 0
        emo = st.selectbox("Emotional state override", options=emo_options, index=emo_idx, key=f"{key_prefix}_emo")
    with c2:
        fatigue_delta = st.number_input("Fatigue delta", step=1, value=int(existing_effect.get("fatigue_delta", 0)), key=f"{key_prefix}_fatigue_delta")
        morale_delta = st.number_input("Morale delta", step=1, value=int(existing_effect.get("morale_delta", 0)), key=f"{key_prefix}_morale_delta")
        mem_inject = st.text_area(
            "Memory inject", value=existing_effect.get("memory_inject", ""),
            height=80, key=f"{key_prefix}_mem",
            help="Text injected into the agent's memory buffer on USE.",
        )
    result = {}
    if perc_delta:
        result["perception_delta"] = int(perc_delta)
    if health_delta:
        result["health_delta"] = int(health_delta)
    if stress_delta:
        result["stress_delta"] = int(stress_delta)
    if fatigue_delta:
        result["fatigue_delta"] = int(fatigue_delta)
    if morale_delta:
        result["morale_delta"] = int(morale_delta)
    if emo:
        result["emotional_state"] = emo
    if mem_inject.strip():
        result["memory_inject"] = mem_inject.strip()
    return result


def render_tab_items() -> None:
    if not _ss().se_scenario_dir:
        st.info("Load or create a scenario first.")
        return

    loc_options = _location_options()
    inline_items: dict = _world().setdefault("items", {})
    placements: list = _world().setdefault("item_placements", [])
    library_items: dict = _library().get("items", {})

    inline_tab, library_tab = st.tabs(["Inline Items", "Library Placements"])

    # ---- Inline items ----
    with inline_tab:
        st.caption("Items defined directly in this scenario's world_state.json.")

        to_delete = None
        for item_id, item in list(inline_items.items()):
            with st.expander(f"{item.get('name', item_id)} ({item_id})", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    n_name = st.text_input("Name", value=item.get("name", ""), key=f"item_name_{item_id}")
                    loc_idx = loc_options.index(item.get("location", "")) if item.get("location") in loc_options else 0
                    n_loc = st.selectbox(
                        "Location", options=loc_options, index=loc_idx,
                        format_func=_location_name, key=f"item_loc_{item_id}",
                    ) if loc_options else st.text_input("Location", value=item.get("location", ""), key=f"item_loc_txt_{item_id}")
                    n_portable = st.checkbox("Portable", value=item.get("portable", True), key=f"item_port_{item_id}")
                    n_contested = st.checkbox("Contested", value=item.get("contested", False), key=f"item_cont_{item_id}")
                with c2:
                    n_desc = st.text_area("Description", value=item.get("description", ""), height=80, key=f"item_desc_{item_id}")
                    n_hidden = st.checkbox("Hidden", value=item.get("hidden", False), key=f"item_hid_{item_id}")
                    n_consumable = st.checkbox("Consumable", value=item.get("consumable", False), key=f"item_cons_{item_id}")

                if n_hidden:
                    n_knowledge = st.text_area(
                        "Knowledge (revealed on pickup)", value=item.get("knowledge", ""),
                        height=80, key=f"item_know_{item_id}",
                    )
                else:
                    n_knowledge = ""

                n_effect = {}
                if n_consumable:
                    n_effect = _render_effect_fields(f"item_eff_{item_id}", item.get("effect", {}))

                in_lib = item_id in _library().get("items", {})
                c_apply, c_save_lib, c_del, _ = st.columns([1, 1, 1, 3])
                with c_apply:
                    if st.button("Apply", key=f"item_apply_{item_id}"):
                        updated = {
                            "name": n_name.strip(),
                            "location": n_loc if loc_options else st.session_state.get(f"item_loc_txt_{item_id}", ""),
                            "owner": item.get("owner"),
                            "description": n_desc.strip(),
                            "portable": n_portable,
                        }
                        if n_contested:
                            updated["contested"] = True
                        if n_hidden:
                            updated["hidden"] = True
                            updated["knowledge"] = n_knowledge.strip()
                        if n_consumable:
                            updated["consumable"] = True
                            if n_effect:
                                updated["effect"] = n_effect
                        inline_items[item_id] = updated
                        _mark_dirty()
                        st.rerun()
                with c_save_lib:
                    save_label = "Update Library" if in_lib else "Save to Library"
                    if st.button(save_label, key=f"item_to_lib_{item_id}"):
                        lib = _library()
                        # Strip placement-specific fields before saving to library
                        lib_entry = {
                            "name": n_name.strip(),
                            "description": n_desc.strip(),
                            "portable": n_portable,
                        }
                        if n_contested:
                            lib_entry["contested"] = True
                        if n_hidden:
                            lib_entry["hidden"] = True
                            if n_knowledge.strip():
                                lib_entry["knowledge"] = n_knowledge.strip()
                        if n_consumable:
                            lib_entry["consumable"] = True
                            if n_effect:
                                lib_entry["effect"] = n_effect
                        lib["items"][item_id] = lib_entry
                        save_item_library(lib)
                        st.session_state.se_item_library = lib
                        st.success(f"{'Updated' if in_lib else 'Saved'} '{item_id}' in library.")
                        st.rerun()
                with c_del:
                    if st.button("Remove", key=f"item_del_{item_id}", type="secondary"):
                        to_delete = item_id

        if to_delete:
            del inline_items[to_delete]
            _mark_dirty()
            st.rerun()

        st.divider()
        with st.expander("➕ Add Inline Item", expanded=False):
            fc1, fc2 = st.columns(2)
            with fc1:
                f_id = st.text_input("Item ID* (snake_case)", help="Unique key, e.g. soda_can", key="new_item_id")
                f_name = st.text_input("Name*", key="new_item_name")
                f_loc = st.selectbox("Location", options=loc_options, format_func=_location_name, key="new_item_loc") if loc_options else st.text_input("Location", key="new_item_loc_txt")
                f_portable = st.checkbox("Portable", value=True, key="new_item_portable")
                f_contested = st.checkbox("Contested", key="new_item_contested")
            with fc2:
                f_desc = st.text_area("Description", height=80, key="new_item_desc")
                f_hidden = st.checkbox("Hidden", key="new_item_hidden")
                f_consumable = st.checkbox("Consumable", key="new_item_consumable")

            if f_hidden:
                f_knowledge = st.text_area("Knowledge (revealed on pickup)", height=60, key="new_item_knowledge")
            else:
                f_knowledge = ""

            f_effect = {}
            if f_consumable:
                f_effect = _render_effect_fields("new_item_effect", {})

            if st.button("Add Item", key="new_item_submit"):
                clean_id = f_id.strip()
                if not clean_id or not f_name.strip():
                    st.error("Item ID and Name are required.")
                elif clean_id in inline_items:
                    st.error(f"Item ID '{clean_id}' already exists.")
                else:
                    entry = {
                        "name": f_name.strip(),
                        "location": f_loc if loc_options else st.session_state.get("new_item_loc_txt", ""),
                        "owner": None,
                        "description": f_desc.strip(),
                        "portable": f_portable,
                    }
                    if f_contested:
                        entry["contested"] = True
                    if f_hidden:
                        entry["hidden"] = True
                        entry["knowledge"] = f_knowledge.strip()
                    if f_consumable:
                        entry["consumable"] = True
                        if f_effect:
                            entry["effect"] = f_effect
                    inline_items[clean_id] = entry
                    _mark_dirty()
                    st.rerun()

    # ---- Library placements ----
    with library_tab:
        st.caption("Items pulled from the shared library and placed in this scenario.")

        inline_ids = set(inline_items.keys())
        to_remove_idx = None

        for p_idx, placement in enumerate(placements):
            pid = placement["item_id"]
            lib_entry = library_items.get(pid, {})
            shadowed = pid in inline_ids
            label = lib_entry.get("name", pid)
            if shadowed:
                label += " ⚠ shadowed by inline item"
            with st.expander(f"{label} ({pid}) @ {_location_name(placement.get('location', ''))}", expanded=False):
                if shadowed:
                    st.warning(f"An inline item with ID '{pid}' already exists. This placement will be ignored at runtime.")

                st.caption(lib_entry.get("description", "No description in library."))

                loc_idx = loc_options.index(placement.get("location", "")) if placement.get("location") in loc_options else 0
                n_loc = st.selectbox(
                    "Location", options=loc_options, index=loc_idx,
                    format_func=_location_name, key=f"plc_loc_{p_idx}",
                ) if loc_options else st.text_input("Location", value=placement.get("location", ""), key=f"plc_loc_txt_{p_idx}")

                # Show override options based on what the library item supports
                lib_is_hidden = lib_entry.get("hidden", False)
                override_contested = st.checkbox(
                    "Override: Contested", value=placement.get("contested", lib_entry.get("contested", False)),
                    key=f"plc_cont_{p_idx}",
                )
                override_hidden = st.checkbox(
                    "Override: Hidden", value=placement.get("hidden", lib_is_hidden),
                    key=f"plc_hid_{p_idx}",
                )
                knowledge_override = ""
                if override_hidden:
                    knowledge_override = st.text_area(
                        "Knowledge override",
                        value=placement.get("knowledge", lib_entry.get("knowledge", "")),
                        height=80, key=f"plc_know_{p_idx}",
                        help="Overrides the library's default knowledge text.",
                    )

                c_apply, c_rem, _ = st.columns([1, 1, 4])
                with c_apply:
                    if st.button("Apply", key=f"plc_apply_{p_idx}"):
                        updated_plc = {"item_id": pid, "location": n_loc if loc_options else st.session_state.get(f"plc_loc_txt_{p_idx}", "")}
                        if override_contested:
                            updated_plc["contested"] = True
                        if override_hidden:
                            updated_plc["hidden"] = True
                            if knowledge_override.strip():
                                updated_plc["knowledge"] = knowledge_override.strip()
                        placements[p_idx] = updated_plc
                        _mark_dirty()
                        st.rerun()
                with c_rem:
                    if st.button("Remove", key=f"plc_rem_{p_idx}", type="secondary"):
                        to_remove_idx = p_idx

        if to_remove_idx is not None:
            placements.pop(to_remove_idx)
            _mark_dirty()
            st.rerun()

        st.divider()
        with st.expander("➕ Place Library Item", expanded=False):
            already_placed_ids = {p["item_id"] for p in placements}
            available_lib = [iid for iid in library_items if iid not in already_placed_ids]
            if not available_lib:
                st.info("All library items are already placed.")
            elif not loc_options:
                st.info("Add locations first.")
            else:
                with st.form("form_place_lib_item"):
                    f_lib_id = st.selectbox(
                        "Library item",
                        options=available_lib,
                        format_func=lambda x: f"{library_items[x].get('name', x)} ({x})",
                    )
                    f_plc_loc = st.selectbox("Location", options=loc_options, format_func=_location_name)
                    f_plc_cont = st.checkbox("Contested override")
                    submitted = st.form_submit_button("Place")
                    if submitted:
                        new_plc: dict = {"item_id": f_lib_id, "location": f_plc_loc}
                        if f_plc_cont:
                            new_plc["contested"] = True
                        placements.append(new_plc)
                        _mark_dirty()
                        st.rerun()

# ---------------------------------------------------------------------------
# Tab 5 — Locations
# ---------------------------------------------------------------------------

def render_tab_locations() -> None:
    if not _ss().se_scenario_dir:
        st.info("Load or create a scenario first.")
        return

    locations: dict = _world().setdefault("locations", {})
    all_loc_ids = list(locations.keys())
    to_delete_loc = None

    for loc_id, loc in list(locations.items()):
        with st.expander(f"{loc.get('name', loc_id)} ({loc_id})", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                n_name = st.text_input("Name", value=loc.get("name", ""), key=f"loc_name_{loc_id}")
                other_locs = [lid for lid in all_loc_ids if lid != loc_id]
                cur_conn = [c for c in loc.get("connected_to", []) if c in other_locs]
                n_conn = st.multiselect(
                    "Connected to",
                    options=other_locs,
                    default=cur_conn,
                    format_func=lambda x: locations.get(x, {}).get("name", x),
                    key=f"loc_conn_{loc_id}",
                )
                status_str = ", ".join(loc.get("status_effects", []))
                n_status = st.text_input(
                    "Status effects (comma-separated)", value=status_str, key=f"loc_se_{loc_id}",
                    help="e.g. radiation_low, high_humidity",
                )
            with c2:
                n_desc = st.text_area("Description", value=loc.get("description", ""), height=130, key=f"loc_desc_{loc_id}")

            # Systems
            st.markdown("**Systems**")
            systems: dict = loc.get("systems", {})
            tool_options = _tool_options()
            sys_to_del = None
            for sys_id, sys_data in list(systems.items()):
                sc1, sc2, sc3, sc4, sc5, sc6 = st.columns([2, 2, 2, 2, 2, 1])
                with sc1:
                    ns_name = st.text_input("Name", value=sys_data.get("name", ""), key=f"sys_name_{loc_id}_{sys_id}")
                with sc2:
                    cur_status = sys_data.get("status", "ONLINE")
                    ns_status = st.selectbox(
                        "Status", options=SYSTEM_STATUSES,
                        index=SYSTEM_STATUSES.index(cur_status) if cur_status in SYSTEM_STATUSES else 0,
                        key=f"sys_status_{loc_id}_{sys_id}",
                    )
                with sc3:
                    ns_desc = st.text_input("Description", value=sys_data.get("description", ""), key=f"sys_desc_{loc_id}_{sys_id}")
                with sc4:
                    current_repair_tool = sys_data.get("required_tool_repair", sys_data.get("required_tool", ""))
                    ns_repair_tool = st.selectbox(
                        "Repair Tool",
                        options=tool_options,
                        index=tool_options.index(current_repair_tool) if current_repair_tool in tool_options else 0,
                        format_func=_tool_label,
                        key=f"sys_repair_tool_{loc_id}_{sys_id}"
                    )
                with sc5:
                    current_sabotage_tool = sys_data.get("required_tool_sabotage", "")
                    ns_sabotage_tool = st.selectbox(
                        "Sabotage Tool",
                        options=tool_options,
                        index=tool_options.index(current_sabotage_tool) if current_sabotage_tool in tool_options else 0,
                        format_func=_tool_label,
                        key=f"sys_sabotage_tool_{loc_id}_{sys_id}"
                    )
                with sc6:
                    if st.button("✕", key=f"sys_del_{loc_id}_{sys_id}"):
                        sys_to_del = sys_id

            if sys_to_del:
                del systems[sys_to_del]
                loc["systems"] = systems
                _mark_dirty()
                st.rerun()

            with st.form(f"form_add_sys_{loc_id}"):
                sa1, sa2, sa3, sa4, sa5, sa6 = st.columns([2, 2, 3, 1, 2, 2])
                with sa1:
                    fs_id = st.text_input("System ID", help="e.g. oxygen_generator")
                with sa2:
                    fs_name = st.text_input("System Name")
                with sa3:
                    fs_desc = st.text_input("Description")
                with sa4:
                    fs_status = st.selectbox("Status", options=SYSTEM_STATUSES)
                with sa5:
                    fs_repair_tool = st.selectbox("Repair Tool", options=tool_options, format_func=_tool_label)
                with sa6:
                    fs_sabotage_tool = st.selectbox("Sabotage Tool", options=tool_options, format_func=_tool_label)
                if st.form_submit_button("Add System"):
                    if fs_id.strip() and fs_name.strip():
                        new_system = {
                            "name": fs_name.strip(),
                            "status": fs_status,
                            "description": fs_desc.strip(),
                        }
                        if fs_repair_tool.strip():
                            new_system["required_tool_repair"] = fs_repair_tool.strip()
                        if fs_sabotage_tool.strip():
                            new_system["required_tool_sabotage"] = fs_sabotage_tool.strip()
                        systems[fs_id.strip()] = new_system
                        locations[loc_id].setdefault("systems", {}).update(systems)
                        _mark_dirty()
                        st.rerun()

            # Sync system edits before applying location
            for sys_id in list(systems.keys()):
                sys_name_val = st.session_state.get(f"sys_name_{loc_id}_{sys_id}", systems[sys_id].get("name", ""))
                sys_status_val = st.session_state.get(f"sys_status_{loc_id}_{sys_id}", systems[sys_id].get("status", "ONLINE"))
                sys_desc_val = st.session_state.get(f"sys_desc_{loc_id}_{sys_id}", systems[sys_id].get("description", ""))
                sys_repair_tool_val = st.session_state.get(
                    f"sys_repair_tool_{loc_id}_{sys_id}",
                    systems[sys_id].get("required_tool_repair", systems[sys_id].get("required_tool", ""))
                )
                sys_sabotage_tool_val = st.session_state.get(
                    f"sys_sabotage_tool_{loc_id}_{sys_id}",
                    systems[sys_id].get("required_tool_sabotage", "")
                )
                updated_system = {"name": sys_name_val, "status": sys_status_val, "description": sys_desc_val}
                if str(sys_repair_tool_val).strip():
                    updated_system["required_tool_repair"] = str(sys_repair_tool_val).strip()
                if str(sys_sabotage_tool_val).strip():
                    updated_system["required_tool_sabotage"] = str(sys_sabotage_tool_val).strip()
                for consequence_key in ("consequences", "effects_when_broken", "effects_when_online", "effects_when_offline", "effects_when_degraded"):
                    if consequence_key in systems[sys_id]:
                        updated_system[consequence_key] = systems[sys_id][consequence_key]
                systems[sys_id] = updated_system

            c_apply, c_del, _ = st.columns([1, 1, 4])
            with c_apply:
                if st.button("Apply", key=f"loc_apply_{loc_id}"):
                    status_effects = [s.strip() for s in n_status.split(",") if s.strip()]
                    locations[loc_id] = {
                        "name": n_name.strip(),
                        "description": n_desc.strip(),
                        "connected_to": n_conn,
                        "status_effects": status_effects,
                    }
                    for access_key in ("requires_item", "requires_items", "access_denied_message", "access_denied_memory"):
                        if access_key in loc:
                            locations[loc_id][access_key] = loc[access_key]
                    if systems:
                        locations[loc_id]["systems"] = systems
                    _mark_dirty()
                    st.rerun()
            with c_del:
                if st.button("Delete", key=f"loc_del_{loc_id}", type="secondary"):
                    # Check for slots referencing this location
                    using_slots = [s["slot_id"] for s in _slots().get("slots", []) if s.get("starting_location") == loc_id]
                    if using_slots:
                        st.error(f"Cannot delete: used as starting location for slots {using_slots}.")
                    else:
                        to_delete_loc = loc_id

    if to_delete_loc:
        # Remove from other locations' connected_to
        for lid, ldata in locations.items():
            if lid != to_delete_loc:
                ldata["connected_to"] = [c for c in ldata.get("connected_to", []) if c != to_delete_loc]
        del locations[to_delete_loc]
        _mark_dirty()
        st.rerun()

    st.divider()
    with st.expander("➕ Add Location", expanded=False):
        with st.form("form_add_loc"):
            fl1, fl2 = st.columns(2)
            with fl1:
                f_loc_name = st.text_input("Name*")
                f_loc_conn = st.multiselect(
                    "Connected to",
                    options=all_loc_ids,
                    format_func=lambda x: locations.get(x, {}).get("name", x),
                )
                f_loc_se = st.text_input("Status effects (comma-separated)")
            with fl2:
                f_loc_desc = st.text_area("Description", height=100)
            submitted = st.form_submit_button("Add Location")
            if submitted:
                if not f_loc_name.strip():
                    st.error("Name is required.")
                else:
                    new_lid = _slugify(f_loc_name)
                    if new_lid in locations:
                        st.error(f"Location ID '{new_lid}' already exists.")
                    else:
                        se_list = [s.strip() for s in f_loc_se.split(",") if s.strip()]
                        locations[new_lid] = {
                            "name": f_loc_name.strip(),
                            "description": f_loc_desc.strip(),
                            "connected_to": f_loc_conn,
                            "status_effects": se_list,
                        }
                        # Add reverse connections
                        for conn_id in f_loc_conn:
                            if conn_id in locations:
                                if new_lid not in locations[conn_id].get("connected_to", []):
                                    locations[conn_id].setdefault("connected_to", []).append(new_lid)
                        _mark_dirty()
                        st.rerun()

# ---------------------------------------------------------------------------
# Tab 6 — Relationships
# ---------------------------------------------------------------------------

def render_tab_relationships() -> None:
    if not _ss().se_scenario_dir:
        st.info("Load or create a scenario first.")
        return

    active_def_ids = _active_slot_def_ids()
    if len(active_def_ids) < 2:
        st.info("Add at least two simulation slots to configure relationships.")
        return

    def_map = _definition_map()
    preset_names = _preset_names()
    preset_descriptions = {k: v.get("description", "") for k, v in _presets().get("presets", {}).items()}
    relationships: list = _slots().setdefault("relationships", [])
    rel_map: dict = {(r["from"], r["to"]): r["preset"] for r in relationships}

    st.caption("Set starting relationship state between each pair of active agents. Changes apply to all pairs on save.")

    # Display each agent's outgoing relationships in an expander
    changed = False
    new_rel_map = dict(rel_map)

    for from_id in active_def_ids:
        from_name = def_map.get(from_id, {}).get("name", from_id)
        with st.expander(f"{from_name}'s view of others", expanded=False):
            for to_id in active_def_ids:
                if from_id == to_id:
                    continue
                to_name = def_map.get(to_id, {}).get("name", to_id)
                cur_preset = rel_map.get((from_id, to_id), "neutral")
                cur_idx = preset_names.index(cur_preset) if cur_preset in preset_names else 0

                col_label, col_sel, col_desc = st.columns([2, 2, 4])
                with col_label:
                    st.markdown(f"→ **{to_name}**")
                with col_sel:
                    chosen = st.selectbox(
                        label="preset",
                        options=preset_names,
                        index=cur_idx,
                        key=f"rel_{from_id}_{to_id}",
                        label_visibility="collapsed",
                    )
                with col_desc:
                    st.caption(preset_descriptions.get(chosen, ""))

                if chosen != cur_preset:
                    new_rel_map[(from_id, to_id)] = chosen
                    changed = True

    if changed or st.button("Apply Relationship Changes"):
        # Rebuild the relationships list, preserving non-active-agent entries
        preserved = [
            r for r in relationships
            if r.get("from") not in active_def_ids or r.get("to") not in active_def_ids
        ]
        rebuilt = [
            {"from": f, "to": t, "preset": p}
            for (f, t), p in new_rel_map.items()
            if f in active_def_ids and t in active_def_ids
        ]
        _slots()["relationships"] = preserved + rebuilt
        _mark_dirty()

    st.divider()
    st.subheader("Current preset reference")
    rows = []
    for pname, pdata in _presets().get("presets", {}).items():
        rows.append({
            "Preset": pname,
            "Trust": pdata.get("trust"),
            "Affinity": pdata.get("affinity"),
            "Suspicion": pdata.get("suspicion"),
            "Description": pdata.get("description", ""),
        })
    if rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows).set_index("Preset"), width="stretch")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(*, embedded: bool = False) -> None:
    render_sidebar()

    if embedded:
        st.title("🛠 Scenario Editor")
    else:
        st.title("Scenario Editor")

    if not _ss().se_scenario_dir:
        st.info("Use the sidebar to load an existing scenario or create a new one.")
        return

    manifest_name = _ss().se_scenario_manifest.get("name") or Path(_ss().se_scenario_dir).name
    dirty_marker = " ●" if _ss().se_dirty else ""
    st.subheader(f"{manifest_name}{dirty_marker}")

    tab_meta, tab_agents, tab_slots, tab_items, tab_locs, tab_rels = st.tabs([
        "Scenario", "Agent Definitions", "Simulation Slots",
        "Items", "Locations", "Relationships",
    ])

    with tab_meta:
        render_tab_scenario()
    with tab_agents:
        render_tab_agents()
    with tab_slots:
        render_tab_slots()
    with tab_items:
        render_tab_items()
    with tab_locs:
        render_tab_locations()
    with tab_rels:
        render_tab_relationships()


if __name__ == "__main__":
    configure_page()
    main()
