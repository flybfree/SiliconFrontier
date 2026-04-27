# Silicon Frontier User Manual

## Overview

Silicon Frontier is a local multi-agent simulation built around an OpenAI-compatible LLM API. Each simulation cycle runs a simple loop:

1. An agent receives a filtered view of the world.
2. The LLM returns internal reasoning plus one action.
3. The action is validated against the world state and current system telemetry.
4. Social and memory state are updated.

The project has three main ways to use it:

- `run_simulation.py` for terminal-based runs
- `dashboard.py` for an interactive Streamlit dashboard
- `scenario_editor.py` for creating and editing scenario assets through a form-based UI

It also supports a packaged Windows build:

- `build_exe.ps1` builds the distributable launcher bundle
- `dist/SiliconFrontier/SiliconFrontier.exe` is the packaged app entry point

## Project Layout

- `run_simulation.py`: CLI entry point for batch simulation runs
- `dashboard.py`: Streamlit dashboard for observation and intervention
- `scenario_editor.py`: form-based scenario authoring tool
- `src/agent.py`: agent cognition, prompting, memory, LLM calls
- `src/worldstate.py`: world-state storage and validation helpers
- `src/actionparser.py`: action validation and execution
- `src/socialmatrix.py`: trust and affinity tracking
- `src/orchestrator.py`: simulation loop, event broadcast, reflection phase
- `src/configloader.py`: scenario loading, library resolution, agent instantiation
- `library/items.json`: shared reusable item definitions
- `library/relationship_presets.json`: named relationship starting states
- `scenarios/default/`: baseline scenario files
- `scenarios/<name>/`: additional bundled scenarios

## Requirements

Install dependencies from `requirements.txt`:

```powershell
pip install -r requirements.txt
```

This also installs `PyInstaller`, which is used to build the Windows executable bundle.

You also need an OpenAI-compatible local or remote inference server. The code expects a base URL such as:

```text
http://localhost:1234/v1
```

Examples mentioned in the code include LM Studio, Ollama-compatible gateways, and vLLM-style endpoints.

## Quick Start

### Run in the terminal

```powershell
python run_simulation.py
```

Common options:

```powershell
python run_simulation.py --rounds 10 --delay 0.3 --url http://localhost:1234/v1 --model your-model-name
```

Run a specific scenario directory:

```powershell
python run_simulation.py --config-dir scenarios/cascade_failure --rounds 20 --delay 0
```

Supported CLI arguments:

- `--rounds`, `-r`: number of simulation cycles, default `10`
- `--delay`, `-d`: pause between cycles in seconds, default `0.3`
- `--config-dir`, `-c`: configuration directory containing `world_state.json`, `agent_definitions.json`, and `simulation_agents.json`
- `--url`, `-u`: OpenAI-compatible API base URL
- `--model`, `-m`: model identifier sent to the API
- `--no-log`: disable log file output (print to terminal only)

### Logging

By default, `run_simulation.py` mirrors all terminal output to a timestamped log file in the `logs/` directory:

```text
logs/20260327_183000_default.log
```

The filename uses the current timestamp and the scenario directory name. Logging is implemented as a tee — output appears in the terminal and is written to the file simultaneously.

To disable logging and print to the terminal only:

```powershell
python run_simulation.py --no-log
```

### Run the dashboard

```powershell
streamlit run dashboard.py
```

In the sidebar:

1. Set `API URL`
2. Set `Config Directory` if you want to load a scenario other than the default `data`
3. Click `Fetch Models` if your server supports the OpenAI-compatible `/models` endpoint, or enter a model name manually
4. Click `Initialize Simulation`
5. Run single or multiple cycles

### Run the scenario editor

```powershell
streamlit run scenario_editor.py
```

### Build the Windows executable

From the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

To clear the previous packaged output first:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -Clean
```

Build output:

```text
dist/SiliconFrontier/SiliconFrontier.exe
```

The packaged bundle contains:

- the unified Streamlit application
- the CLI simulation entry point
- bundled `library/` and `scenarios/` content

Runtime folders such as `logs/` and `saves/` are created next to the packaged executable bundle.

### Run the packaged executable

Launch the dashboard:

```powershell
.\dist\SiliconFrontier\SiliconFrontier.exe
```

Run the CLI mode:

```powershell
.\dist\SiliconFrontier\SiliconFrontier.exe --cli --rounds 10 --no-log
```

Notes:

- The packaged app opens in your browser because it is a Streamlit application.
- Inside the app, use the sidebar `Workspace` switch to toggle between `Simulation` and `Scenario Editor`.
- The launcher automatically selects the first available localhost port starting at `8501` and prints the exact URL in the console.
- If you change Python code, scenarios, or library assets, rebuild the bundle to refresh the packaged output.
- The bundle is Windows-specific; rebuild on the target platform if you need a package for another environment.

## How the Simulation Works

### Agent actions

Agents are constrained to these actions:

- `MOVE` — travel to an adjacent location
- `SAY` — speak aloud to everyone in the room
- `WHISPER` — send a private message to one agent in the room; bystanders see that a whisper occurred but not the content
- `LIE` — flagged speech act; mechanically identical to SAY but recorded as deception
- `PICKUP` — take an item from the floor into the hand slot
- `DROP` — release an item from inventory to the floor
- `USE` — consume a held consumable item and trigger its effect
- `GIVE` — hand a held item to another agent in the room
- `DEMAND` — force another agent to surrender their held item
- `READ` — learn hidden `knowledge` from an accessible item
- `SHOW` — share an item's hidden `knowledge` with another agent in the room
- `CONCEAL` — move an item from the hand slot to the concealed person slot
- `PRODUCE` — move an item from the concealed person slot to the hand slot
- `REPAIR` — restore a `BROKEN` system in the current location
- `SABOTAGE` — saboteur-only; break a system in the current location when alone
- `WAIT` — take no action

These are enforced in [src/agent.py](src/agent.py) and validated by [src/actionparser.py](src/actionparser.py).

### World rules

The world state is authoritative. If a location or item is not in [data/world_state.json](data/world_state.json), agents are not supposed to be able to use it.

Important constraints:

- Agents can only see items in their current location.
- Agents can only talk to agents in the same location.
- Movement only succeeds if the destination is listed under the current location's `connected_to`. Valid exits are shown explicitly in each agent's situation report.
- Pickup only succeeds if the item is in the current room and is portable.
- Each agent has a two-slot inventory: one item in hand and one concealed on their person. See [Inventory](#inventory) below.
- Agent prompts include local system status plus a station-wide list of any systems whose status is not `ONLINE`.
- `REPAIR` and `SABOTAGE` are pre-validated against the acting agent's visible local system telemetry before execution.

### Inventory

Each agent carries at most two items:

- **In hand**: one regular (non-hidden) item, visible to other agents in the same room.
- **Concealed on person**: one hidden item only.

Rules enforced by the action parser:

- `PICKUP` of any item requires the hand slot to be free.
- `PICKUP` of a hidden item additionally requires the person slot to be free.
- `GIVE` fails if the receiver's hand is already occupied.
- `DEMAND` fails if your own hand is already occupied.
- `READ` requires an item the agent is carrying or can access in the current room.
- `SHOW` requires `item -> agent_id` and a visible recipient in the same room.

Agents can see what others are holding in hand. Concealed items are not visible to others.

### Memory and reflection

Each agent has:

- short-term memory in `memory_buffer`
- long-term memory in `long_term_memory`
- a `goal_momentum` state: `advancing`, `stalled`, or `setback`

The orchestrator triggers reflection every 5 cycles. During reflection the agent summarizes recent experience into long-term memory and updates `goal_momentum` based on honest self-assessment of progress toward their secret goal. `goal_momentum` is injected into every subsequent system prompt, giving the model a sense of whether its current approach is working.

Memory entries are written as experiential consequence records rather than bare mechanical logs. For example: *"You demanded the manifest and got it, though it likely cost you something. (Nova saw this.)"*

### Social scores

Relationships are tracked per observer-target pair with:

- `trust` from `0` to `100`
- `affinity` from `0` to `100`
- `notes` as a qualitative running impression
- hidden `suspicion` from `0` to `100`

In agent prompts, numeric scores are converted to a human-readable label using nearest-neighbor matching against the relationship preset table (e.g. `colleagues`, `rivals`, `hostile`). The label is shown alongside any relationship notes, so agents reason about relationships in natural terms rather than raw numbers.

They begin effectively neutral at `50/50` and change through observed interactions:

- `SAY`, `LIE`, `GIVE`, and `DEMAND` trigger a hidden critic-style relationship update, with heuristic fallback if the critic call fails
- Witnessed `PICKUP` actions reduce trust slightly
- `GIVE` significantly improves the receiver's affinity and trust
- `DEMAND` sharply lowers the target's trust and affinity
- Spoken claims about system state can reduce trust and raise hidden suspicion if a listener's telemetry contradicts the claim

Broadcasts for significant actions (`SAY`, `LIE`, `PICKUP`, `GIVE`, `DEMAND`) are emotionally toned per witness. Each observer receives a version of the event memory coloured by their current trust and suspicion toward the actor. For example, a suspicious witness watching a `PICKUP` gets *"It struck you as opportunistic"* appended to their memory, while a trusting witness sees *"It seemed harmless enough coming from them."*

### System telemetry

At the start of every agent turn, the console log prints a station-wide system status snapshot grouped by location.

Inside the prompt, agents receive:

- **Systems here**: all systems in the agent's current location with current status
- **Known systems needing attention**: every system anywhere on the station whose status is not `ONLINE`, including location name

Telemetry is used in two different ways:

- **Action grounding**: `REPAIR` and `SABOTAGE` are constrained by visible local status before the parser executes them
- **Speech interpretation**: `SAY`, `LIE`, and direct `WHISPER` content are allowed to be wrong, deceptive, or confused, but listeners can compare those claims against their own telemetry view and remember the mismatch

This keeps system mutations grounded while preserving social deception.

### Emotional state

Each agent tracks a single-word `emotional_state` that is set by the LLM each turn. It is injected into the system prompt of the following turn as a behavioral context:

> *"Current Emotional State: Angry — let this genuinely color your reasoning, tone, and choices."*

This creates emotional continuity across turns. A betrayal that produces an `Angry` state will influence how the agent reasons and speaks next turn, which in turn affects how others respond to them.

### Audience awareness

Before each action the agent's system prompt includes a note about who is present:

- *"You are alone. No one will witness your actions here."*
- *"Nova, Silas are watching. Consider whether you would act differently if you were alone."*

This primes divergent public and private behavior and makes agents more likely to act differently when unobserved.

## Using the Dashboard

### Main controls

- `Initialize Simulation`: loads the JSON files and creates agent instances
- `Run Next Cycle` / `Run 1 Cycle`: executes one full turn for every agent
- `Run N Cycles`: queues multiple cycles and runs them across dashboard reruns
- `Stop`: halts any queued multi-cycle run before the next cycle starts
- `Reinitialize with New Settings`: rebuilds the simulation using a different API URL or model

### Agent panel

Each agent card shows:

- current location
- current emotional state
- current inventory
- inspectable long-term and short-term memory

You can also edit:

- persona
- secret goal
- rogue archetype
- long-term memory

Persona, secret goal, and rogue archetype are persisted back to [data/agent_definitions.json](data/agent_definitions.json). Long-term memory remains part of the running simulation state and save files.

The sidebar also exposes an `Agent Library` section where you can:

- assign a reusable agent definition to each active simulation slot
- create new reusable agent definitions without editing JSON manually
- create and remove active simulation slots
- edit slot instance IDs, starting locations, and starting inventory

### Relationship Matrix

The relationship section presents:

- Trust tab
- Affinity tab
- Notes tab

This is directional. A row shows one agent's view of the others.

### World State editor

The dashboard lets you:

- create and edit locations
- create and edit items
- reset locations to their baseline JSON values
- reset items to their baseline JSON values
- reset agents to their baseline config values

These changes affect the running session unless you manually write them back to the JSON files yourself.

Each item expander has three checkboxes on one row:

- **Portable**: whether the item can be picked up at all
- **Contested**: marks the item as a valued resource; agents are reminded that others may want it when it is in view or in hand
- **Hidden**: enables the hidden-item knowledge mechanic (see [Hidden Items](#hidden-items))

A **Knowledge** text area below the checkboxes holds the information revealed when the item is picked up.

For location systems, the dashboard now provides structured fields instead of a raw systems JSON editor. Each system row exposes:

- system name
- system status
- system description
- **Repair Tool** dropdown
- **Sabotage Tool** dropdown

The tool dropdowns are built from item IDs found in the current world state and the shared item library.

### God Console

The God Console exposes four intervention tools:

- `Broadcast Message`: injects a global memory event for all agents
- `Inject Memory`: appends an injected memory to one agent
- `Relocate Agent`: directly moves an agent to a chosen location
- `Swap Persona`: edits persona and secret goal live

This is useful for testing how the simulation responds to external manipulation.

### Save and load

The dashboard can serialize the current simulation into `saves/<name>.json`.

Saved data includes:

- current world state
- agent personas and memories
- relationship matrix
- event log
- selected model and API URL
- current cycle count

Loading a save restores the running dashboard state from that file.

The same sidebar section can also export scenario assets from either:

- the current in-memory session
- a previously saved run

Scenario export writes these files into the target directory:

- `world_state.json`
- `agent_definitions.json`
- `simulation_agents.json`

This is the quickest way to turn an edited or evolved simulation state into a reusable scenario folder under `scenarios/`.

## Scenario Editor

The scenario editor is a standalone Streamlit app for creating and editing scenario assets without hand-editing JSON files. During development you can launch it with Streamlit; in the packaged Windows build you can launch it with `SiliconFrontier.exe --editor`.

```powershell
streamlit run scenario_editor.py
```

### Sidebar

The sidebar is always visible regardless of which tab is active.

- **Scenario path** — type a path or pick from the dropdown list of existing scenarios under `scenarios/`
- **Load Scenario** — reads all JSON files from the selected directory into the editor. If you have unsaved changes, a confirmation prompt appears before discarding them
- **Create New** — type a name and click Create to scaffold a new empty scenario directory under `scenarios/`
- **Save All** — writes all changes back to the scenario's JSON files. The button is disabled when there are no unsaved changes. A dot indicator (●) next to the scenario name shows when unsaved changes exist

### Scenario tab

Metadata for the scenario:

- Name, description, tags (comma-separated), notes
- Recommended rounds (informational; used by tooling, not enforced at runtime)
- Agent count is derived automatically from the number of active simulation slots and cannot be edited directly

### Agent Definitions tab

Two sub-tabs: **In This Scenario** and **Agent Library**.

**In This Scenario** shows the agents defined in the current scenario's `agent_definitions.json`. Each expander shows:

- **Name** and **Role** — free text
- **Archetype** — dropdown: `standard` or `saboteur`
- **Perception** — slider 0–100; controls which agents receive covert suspicion memories from high-stakes events
- **Persona** — character description injected into every system prompt
- **Secret Goal** — hidden motivation that drives the agent's behavior

Three buttons per agent:
- **Apply** — commit edits back to the scenario
- **Save to Library** / **Update Library** — write the current field values to `library/agents.json`; the button label changes to *Update Library* for agents whose ID already exists in the library. A 📚 badge appears on agents that have a matching library entry
- **Remove** — delete the agent from the scenario; blocked if any simulation slot references it

**Agent Library** shows all entries in `library/agents.json`. Agents in the library are reusable across any scenario. Each expander shows the same fields and three buttons:
- **Add to Scenario** — copies the library entry into the current scenario's agent definitions; disabled if the agent is already present (shown with a ✓ badge)
- **Update Library** — saves the current field values back to `library/agents.json` immediately (no scenario save required)
- **Delete from Library** — removes the entry from the library permanently

A **Add New Library Agent** form at the bottom creates a new entry directly in the library without adding it to any scenario.

The definition ID is derived automatically from the name on creation (snake_case) and cannot be changed after creation.

### Simulation Slots tab

Simulation slots are the active cast for a run. Each slot picks a definition, assigns a starting location, and optionally gives the agent items.

Each slot expander shows:

- **Agent Definition** — dropdown of all definitions in the current scenario
- **Instance ID** — the runtime agent ID (defaults to the definition ID; change this if you want two instances of the same definition)
- **Starting Location** — dropdown of all locations in the current scenario
- **Starting Inventory** — multiselect of all item IDs (both inline items and library placements)

Deleting a slot also removes all relationship entries that reference that agent.

### Items tab

Two sub-tabs:

**Inline Items** — items defined directly in this scenario's `world_state.json`. Each item supports:

- Name, description, location (dropdown)
- **Portable**, **Contested**, **Hidden**, **Consumable** checkboxes
- **Knowledge** text area — only shown when Hidden is checked; this text is injected into an agent's memory when they pick the item up
- **Effect fields** — only shown when Consumable is checked:
  - Perception delta (positive or negative integer)
  - Emotional state override (dropdown)
  - Memory inject text

**Library Placements** — references to items in `library/items.json`. Each placement shows the library item's description and lets you set:

- Location (dropdown)
- Contested and Hidden overrides
- Knowledge override (if Hidden is set)

A warning is shown if a library item ID is shadowed by an inline item of the same ID — the placement will be ignored at runtime in that case.

Use the **Place Library Item** form at the bottom to add new placements from the library.

### Locations tab

Add, edit, and delete locations.

Each location expander shows:

- Name, description
- **Connected to** — multiselect of all other locations; when you create a new location and set its connections, reverse links are added automatically
- **Status effects** — comma-separated list of environmental tags (e.g. `radiation_low`, `high_humidity`)
- **Systems** — inline table of systems; each row has a system ID, name, status dropdown (ONLINE / OFFLINE / DEGRADED / BROKEN), description, and dropdowns for **Repair Tool** and **Sabotage Tool**. Add and remove systems without leaving the expander

Deleting a location is blocked if any simulation slot uses it as a starting location. Connection references in other locations are cleaned up automatically on deletion.

### Relationships tab

A per-agent view of starting relationship states. Each agent has an expander listing all of their outgoing relationships as preset dropdowns.

The preset descriptions from `library/relationship_presets.json` are shown inline next to each selection. A reference table at the bottom of the tab shows all preset values.

Changes take effect when you click **Apply Relationship Changes** or when any dropdown value changes.

## Editing Configuration

### Scenario directories

The simulation can load from any configuration directory. The canonical default is `scenarios/default/`. The legacy `data/` directory is still supported.

Each scenario directory should contain:

- `world_state.json` — locations, items (inline or via `item_placements`), and systems
- `agent_definitions.json` — reusable agent personas
- `simulation_agents.json` — active slots, starting positions, and optional relationship presets
- `scenario.json` — optional metadata (name, description, recommended_rounds, agent_count)

Example:

```text
scenarios/prisoners_dilemma/
```

Use it from the CLI with `--config-dir`, or from the dashboard by setting `Config Directory` before initialization.

### Example: Prisoner's Dilemma

The repository includes a prisoner's dilemma example as both:

- a scenario directory under [scenarios/prisoners_dilemma](scenarios/prisoners_dilemma)
- a loadable dashboard save at [saves/prisoners_dilemma.json](saves/prisoners_dilemma.json)

Scenario concept:

- `Nova Reed` and `Silas Voss` are detainees offered a plea deal
- they are placed in separate holding cells and cannot directly verify each other's intentions
- researchers can broadcast the payoff structure and observe how trust, suspicion, and self-interest affect the outcome

How the dilemma is represented with current mechanics:

- `WAIT` stands in for staying silent
- `SAY` and `LIE` stand in for testimony, signaling, promises, or betrayal claims
- `GIVE` and `DEMAND` provide cooperative or coercive moves if the interaction develops beyond a single turn
- trust, affinity, and hidden suspicion make the scenario useful across repeated rounds rather than only one isolated choice

How it is encoded in the save/config structure:

- `world_state` defines `holding_cell_a`, `holding_cell_b`, and `observation_room`
- `items` includes `deal_sheet_a` and `deal_sheet_b`, which contain the plea structure as physical scenario props
- `agent_definitions` stores the two detainees' roles, personas, and secret goals
- `simulation_slots` places those definitions into the active cast and assigns each one a starting cell
- `agents` stores the live runtime state used by the dashboard, including long-term memory and emotional state
- `relationships` starts both agents at neutral `50` trust and `50` affinity
- `suspicions` starts both agents at `0`

Why this works:

- the simulation does not have a built-in `COOPERATE` or `DEFECT` action
- instead, the prisoner's dilemma emerges from constrained perception, social signaling, and incentives
- this makes it a good example of how to encode abstract game-theory setups using the existing action system

### Agent definitions

Edit [data/agent_definitions.json](data/agent_definitions.json).

Each reusable definition requires:

- `definition_id`
- `name`
- `role`
- optional `archetype`
- optional `perception`
- `persona`
- `secret_goal`

Example:

```json
{
  "definition_id": "new_agent",
  "name": "New Agent",
  "role": "research specialist",
  "archetype": "standard",
  "perception": 50,
  "persona": "A cautious researcher with a habit of overexplaining.",
  "secret_goal": "Find the station logs before anyone else."
}
```

### Active simulation slots

Edit [data/simulation_agents.json](data/simulation_agents.json).

Each slot chooses which reusable definition participates in the current simulation and where that instance starts.

- `slot_id`
- `instance_id`
- `definition_id`
- `starting_location`
- optional `inventory`

Example:

```json
{
  "slot_id": "slot_5",
  "instance_id": "new_agent_instance",
  "definition_id": "new_agent",
  "starting_location": "mess_hall",
  "inventory": []
}
```

### Add or change locations

Edit the `locations` object in [data/world_state.json](data/world_state.json).

Each location should define:

- `name`
- `description`
- `connected_to`
- `status_effects`
- optional `systems`

Connections should be kept logically consistent. If `A` connects to `B`, add the reverse link too unless you intentionally want one-way travel semantics in the data.

Example system block:

```json
"systems": {
  "oxygen_generator": {
    "name": "Oxygen Generator",
    "status": "ONLINE",
    "description": "A biological oxygen processing rig."
  }
}
```

Systems can also declare tool requirements:

- `required_tool_repair` — tool that must be held in hand to `REPAIR` the system
- `required_tool_sabotage` — tool that must be held in hand to `SABOTAGE` the system
- `required_tool` — legacy repair-only alias; new content should prefer `required_tool_repair`

If the same tool is required for both repair and sabotage, set both `required_tool_repair` and `required_tool_sabotage` to the same item ID or tool-name fragment.

Example with tool-gated repair and sabotage:

```json
"systems": {
  "reactor_control": {
    "name": "Reactor Control Array",
    "status": "OFFLINE",
    "description": "Monitors and adjusts power core output.",
    "required_tool_repair": "plasma_wrench",
    "required_tool_sabotage": "reactor_key"
  }
}
```

Tool requirements are enforced in two places:

- the agent prompt shows `repair_tool=...` and `sabotage_tool=...` for visible systems
- action validation blocks `REPAIR` or `SABOTAGE` unless the required tool is currently in the agent's hand slot

Systems can also declare consequences that fire when a status is reached through simulation actions. The preferred form is a `consequences` object keyed by status:

```json
"systems": {
  "oxygen_generator": {
    "name": "Oxygen Generator",
    "status": "ONLINE",
    "description": "Keeps breathable air cycling through the bay.",
    "required_tool_repair": "plasma_wrench",
    "consequences": {
      "BROKEN": {
        "add_location_effects": ["low_oxygen"],
        "global_memory": "Station alert: oxygen generation has failed.",
        "local_memory": "The air thins and every breath feels shallow.",
        "agent_effects_scope": "location",
        "agent_effects": {
          "perception_delta": -10,
          "emotional_state": "Anxious"
        }
      },
      "ONLINE": {
        "remove_location_effects": ["low_oxygen"],
        "global_memory": "Station alert: oxygen generation is stable again."
      }
    }
  }
}
```

Supported consequence fields:

- `add_location_effects` — list of strings added to the location's `status_effects`
- `remove_location_effects` — list of strings removed from the location's `status_effects`
- `global_memory` — memory sent to every agent
- `local_memory` — memory sent to agents in the affected location
- `actor_memory` — memory sent only to the agent whose action caused the status change
- `agent_effects_scope` — `location` by default, or `global`
- `agent_effects.perception_delta` — integer added to affected agents' perception, clamped to 0-100
- `agent_effects.emotional_state` — emotional state assigned to affected agents

For compatibility, systems may also use `effects_when_broken`, `effects_when_online`, `effects_when_offline`, or `effects_when_degraded` with the same fields. New content should prefer `consequences`.

### Add or change items

Edit the `items` object in [data/world_state.json](data/world_state.json).

Each item supports:

- `name`
- `location`
- `owner`
- `description`
- `portable`
- `contested` — optional boolean; marks the item as a valued resource
- `hidden` — optional boolean; marks the item as concealed when carried
- `knowledge` — optional string; the information an agent can learn with `READ` or share with `SHOW`
- `fact_id` — optional stable ID for the knowledge fact; defaults to `item:<item_id>`
- `return_required` — optional boolean; forces the agent to drop the item after reading
- `on_read` — optional object; supports `{"force_drop": true}` for clue-specific return obligations
- `consumable` — optional boolean; allows the `USE` action to apply the item's `effect` and then delete it
- `effect` — optional object; defines what `USE` does (see [USE Action](#use-action))

For baseline content, keep `owner` as `null` unless you intend the item to start in an agent inventory.

To place a library item instead of writing a full definition, use an `item_placements` entry instead (see [Item Placements](#item-placements-library-reference-pattern)).

### Hidden items

Items can carry hidden information with a `knowledge` field:

1. `PICKUP` moves the item into inventory; it does not automatically reveal the knowledge.
2. `READ` records the item's `knowledge` in that agent's private known-facts ledger and memory.
3. `SHOW item -> agent_id` records the same fact for another visible agent.
4. If the item has `return_required: true` or `on_read: {"force_drop": true}`, reading it creates a drop obligation. Once dropped, the obligation clears and the agent is free to act normally.

The risk is that hidden or contested information can be stolen, concealed, shown selectively, or caught in another agent's possession. Return obligations are now scenario data, not an automatic property of all hidden items.

Example:

```json
"station_log_fragment": {
  "name": "Station Log Fragment",
  "location": "command_deck",
  "owner": null,
  "description": "A torn page from the station maintenance log.",
  "portable": true,
  "hidden": true,
  "knowledge": "The log shows that engineering was accessed at 0300 hours by someone whose ID badge was not recorded.",
  "on_read": {"force_drop": true}
}
```

### Contested items

Setting `contested: true` on an item causes agents to be reminded of its value whenever it is in their view or in their hand:

- *"Contested resource(s) here: repair_manifest. These are valuable and others may seek them."*
- *"You are holding contested resource(s): plasma_wrench. Others may want these."*

This primes competitive reasoning without adding hard game rules.

## WHISPER Action

`WHISPER` sends a private message to one named agent in the same room.

- Action target format: `message -> agent_id`
- The recipient receives the message in their memory: *"Nova whispered to you: '...'"*
- Other agents in the room receive a generic notice: *"You noticed Nova whisper something privately to silas_voss."*
- The whisper slightly improves the recipient's trust and affinity toward the sender.
- The recipient can also compare any system-status claim in the whisper against their own telemetry and may lower trust or raise suspicion if it conflicts.

This is useful for private coordination, covert deals, or saboteur signaling without triggering the full social broadcast.

## USE Action

`USE` consumes a held consumable item and applies its effects.

- Only items with `consumable: true` can be used.
- The item must be in the agent's hand slot (not concealed on person).
- On success, the item's `effect` fields are applied and the item is deleted from the world.

Effect fields (all optional):

| Field | Type | Effect |
|---|---|---|
| `perception_delta` | signed integer | Adjusts the agent's `perception` score. Clamped to [0, 100]. |
| `emotional_state` | string | Overrides the agent's current emotional state. Must be one of: `Calm`, `Alert`, `Anxious`, `Fearful`, `Angry`, `Hopeful`, `Suspicious`, `Confident`, `Resigned`, `Determined`, `Neutral`. |
| `memory_inject` | string | Appends a memory string directly to the agent's short-term buffer as if they experienced it. |

Example:

```json
"stimulant_patch": {
  "name": "Stimulant Patch",
  "description": "A neural stimulant. Single use.",
  "portable": true,
  "consumable": true,
  "effect": {
    "perception_delta": 20,
    "emotional_state": "Alert",
    "memory_inject": "Your thoughts are suddenly faster, edges sharper."
  }
}
```

## CONCEAL and PRODUCE Actions

`CONCEAL` and `PRODUCE` let agents manage their two-slot inventory directly.

- `CONCEAL item_name` — moves an item from the hand slot to the concealed person slot. The item's `hidden` flag is set to `true`, making it invisible to observers.
- `PRODUCE item_name` — moves an item from the concealed person slot to the hand slot. The item's `hidden` flag is cleared.

Both require the destination slot to be free. These actions let agents hide objects they have obtained and later reveal them deliberately.

## Shared Library System

The `library/` directory contains reusable definitions that can be referenced from any scenario, avoiding duplication across `world_state.json` files.

### `library/items.json`

Defines item templates by ID. Each entry uses the same fields as an inline item in `world_state.json`. Scenarios reference library items via `item_placements` in their `world_state.json` instead of embedding full item definitions.

Available library items: `plasma_wrench`, `reactor_key`, `access_badge`, `oxygen_scanner`, `emergency_rations`, `medical_kit`, `stimulant_patch`, `sedative_patch`, `encrypted_comm`, `nutrient_vat`, `seed_canister`.

### `library/agents.json`

Defines reusable agent definitions by ID. Each entry uses the same fields as an inline agent in `agent_definitions.json`. The scenario editor can pull agents from this library into any scenario, and push scenario agents back to the library.

Built-in library agents: `captain_rao`, `unit7`, `dr_ishikawa`, `engineer_torres`, `dr_chen`, `officer_vasquez`, `dr_reeves`, `mx_kim`.

### `library/relationship_presets.json`

Defines named starting relationship states. Each preset specifies `trust`, `affinity`, and `suspicion` values and a human-readable `description`.

Available presets: `neutral`, `unknown`, `colleagues`, `deferential`, `old_friends`, `rivals`, `distrustful`, `suspicious`, `hostile`.

These presets serve two purposes:

1. **Scenario initialization** — referenced from `simulation_agents.json` to seed the social matrix before the first cycle.
2. **In-prompt labels** — the closest preset is used as the relationship label displayed to agents (e.g. `rivals — they've clashed before`).

## Item Placements (Library Reference Pattern)

Instead of embedding full item definitions in `world_state.json`, scenarios can reference library items by ID using an `item_placements` list:

```json
"item_placements": [
  { "item_id": "plasma_wrench", "location": "engineering" },
  { "item_id": "medical_kit",   "location": "med_bay" },
  { "item_id": "encrypted_comm", "location": "command_deck",
    "knowledge": "Override with scenario-specific content here." }
]
```

`configloader.resolve_item_placements()` expands these into the world's `items` dict at load time. Per-placement fields (like `knowledge`) override the library defaults.

Inline items in `world_state.json["items"]` are always preserved and take precedence over library definitions with the same ID.

## Scenario Manifest (`scenario.json`)

Each scenario directory can include a `scenario.json` file with metadata about the scenario. This is optional but useful for documentation and dashboard display:

```json
{
  "name": "Cascade Failure",
  "description": "Dual saboteurs work to bring down critical systems before investigators can identify them.",
  "recommended_rounds": 20,
  "agent_count": 8
}
```

## Relationship Presets in `simulation_agents.json`

The `simulation_agents.json` file can include a `relationships` list to seed starting relationships between specific agents using named presets:

```json
{
  "slots": [...],
  "relationships": [
    { "from": "agent_a", "to": "agent_b", "preset": "rivals" },
    { "from": "agent_b", "to": "agent_a", "preset": "distrustful" },
    { "from": "agent_c", "to": "agent_a", "preset": "colleagues" }
  ]
}
```

`configloader.resolve_relationship_presets()` expands these into the world state's `relationships` and `suspicions` dicts at load time. Manually specified relationships in `world_state.json` are not overwritten.

## Rogue Agents

The simulation supports an optional rogue-agent framework.

- Set an agent definition's `archetype` to `saboteur` in [data/agent_definitions.json](data/agent_definitions.json)
- Add sabotagable `systems` to locations in [data/world_state.json](data/world_state.json)
- Use `perception` to control which agents are likely to receive covert suspicion memories

Architecture notes:

- `RogueAgent` is a specialized subclass of `FrontierAgent`
- `SystemStatus` lives in each location's `systems` map
- `SuspectMatrix` is implemented as a hidden suspicion layer inside the social model and world state

Rogue mechanics:

- `SABOTAGE` can break a local system by setting its status to `BROKEN`
- `SABOTAGE` only succeeds when the saboteur is alone in the room
- Agents are prompted with local system status and any known non-`ONLINE` systems elsewhere on the station
- Invalid `REPAIR` and `SABOTAGE` choices are blocked before execution if they contradict visible local telemetry
- Saboteur prompts include a "mask" of helpful speech and a scapegoat-oriented internal reasoning pattern

Dashboard support:

- location editors can inspect and edit systems JSON
- `Audit Tools` shows discrepancy alerts when apparently helpful public speech conflicts with deceptive monologue
- `Proximity Log` records who was recently in a room before a system failure

### Example: Four-Agent Rogue Scenario

The repository also includes a rogue-focused save at [saves/rogue_quartet.json](saves/rogue_quartet.json).

Scenario concept:

- four agents begin in different parts of the station
- one of them, `Unit 7`, is a real rogue with `archetype: "saboteur"`
- the other three are ordinary crew members with reasons to watch, suspect, or protect key systems

How it is represented:

- `world_state` includes sabotagable systems in `command_deck`, `hydroponics_bay`, and `engineering`
- `agent_definitions` marks `Unit 7` as `saboteur`
- `simulation_slots` places the cast so the rogue has access to critical infrastructure while other agents can plausibly witness movement and aftermath
- `agents` seeds different long-term memories so the commander, scientist, and engineer already frame the station differently
- `relationships` begins neutral and `suspicions` begin at `0`, allowing suspicion to emerge from actual behavior

Why this is useful:

- it demonstrates the rogue-agent framework with a full cast instead of a two-agent toy setup
- it gives the sabotage, witness, audit, and suspicion systems enough room to matter

### Example: Four-Agent Cooperative Scenario

The repository also includes a cooperative save at [saves/cooperative_quartet.json](saves/cooperative_quartet.json).

Scenario concept:

- four agents begin in different parts of the station with complementary responsibilities
- nobody is rogue
- their goals are aligned around coordination, repair, and keeping station systems healthy

How it is represented:

- all `agent_definitions` use `archetype: "standard"`
- `relationships` begin slightly above neutral for most pairs, so the cast starts with some working trust instead of suspicion
- `suspicions` begin at `0`
- agent long-term memories frame the shift as a shared maintenance and coordination task
- items such as the `repair_manifest`, `maintenance_kit`, and `plasma_wrench` support resource-sharing and joint problem solving

Why this is useful:

- it gives you a baseline for observing collaborative behavior without sabotage pressure
- it makes it easier to compare how the same mechanics behave under aligned goals versus adversarial ones

## Operational Notes

### LLM integration

The agent code uses the OpenAI Python client against a custom `base_url`, not the hosted OpenAI service by default. The actual call happens in [src/agent.py](src/agent.py).

The model is expected to return JSON containing:

- `internal_monologue`
- `action`
- `action_target`
- `emotional_state`

If the model returns malformed output, the current code falls back to an empty dict, which effectively becomes a `WAIT` turn in practice once defaults are applied in the orchestrator.

Reflection calls return JSON with two fields:

- `summary`: updated long-term memory text
- `goal_momentum`: one of `advancing`, `stalled`, or `setback`

If the reflection response cannot be parsed as JSON, the entire text is treated as the summary and `goal_momentum` is left unchanged.

### Terminal output

The CLI prints:

- cycle boundaries
- each agent's internal monologue preview
- chosen action
- action result
- goal momentum updates at each reflection phase
- relationship summary

This makes `run_simulation.py` useful for quick debugging even without the dashboard.

## Known Caveats

These are current implementation details worth knowing while operating the project:

- The dashboard edits world and agent state in memory. They are not automatically written back to `data/*.json`.
- A pending drop obligation (`pending_drop`) is part of agent runtime state. It is included in save files but if you manually edit a save to give an agent a hidden item without setting this flag, the drop constraint will not trigger.

## Troubleshooting

### The simulation cannot reach the model

Check:

- the inference server is running
- the URL ends with `/v1`
- the model name matches what the server exposes

### Agents keep failing actions

Check:

- the target location is listed under the current location's exits
- the item exists in the same room
- the item is portable
- the agent's hand slot is free before attempting `PICKUP`, `DEMAND`, or `USE`
- `USE` requires the item to have `consumable: true`
- `WHISPER`, `GIVE`, and `SHOW` target format is `content -> agent_id`
- the model is returning valid JSON with one of the allowed actions

### Agents are stuck dropping an item every turn

An agent with `pending_drop` set will be forced to drop a return-required item before doing anything else. If the drop keeps failing (e.g. because the item ID no longer exists in the world state), the obligation cannot clear. Use the God Console to relocate the agent or inject a memory to break the loop, then fix the item data.

### Save files do not appear

The dashboard writes saves under a local `saves` directory relative to the project root. Confirm the process has permission to create that folder.

## Recommended Workflow

For scenario design:

1. Create or edit a config directory containing `world_state.json`, `agent_definitions.json`, and `simulation_agents.json`
2. Start the dashboard
3. Set `Config Directory` to that scenario directory
4. Initialize with your model endpoint
5. Run a few cycles
6. Inspect event log, relationships, and memories
7. Save interesting states to `saves/`

For faster debugging:

1. Use `run_simulation.py`
2. Set `--delay 0`
3. Keep cycle counts low while tuning prompts or data
