# Silicon Frontier User Manual

## Overview

Silicon Frontier is a local multi-agent simulation built around an OpenAI-compatible LLM API. Each simulation cycle runs a simple loop:

1. An agent receives a filtered view of the world.
2. The LLM returns internal reasoning plus one action.
3. The action is validated against the world state.
4. Social and memory state are updated.

The project has two main ways to use it:

- `run_simulation.py` for terminal-based runs
- `dashboard.py` for an interactive Streamlit dashboard

## Project Layout

- `run_simulation.py`: CLI entry point for batch simulation runs
- `dashboard.py`: Streamlit dashboard for observation and intervention
- `src/agent.py`: agent cognition, prompting, memory, LLM calls
- `src/worldstate.py`: world-state storage and validation helpers
- `src/actionparser.py`: action validation and execution
- `src/socialmatrix.py`: trust and affinity tracking
- `src/orchestrator.py`: simulation loop, event broadcast, reflection phase
- `data/world_state.json`: locations, items, and baseline world data
- `data/agent_definitions.json`: reusable agent definitions
- `data/simulation_agents.json`: active simulation slots and selected agent definitions

## Requirements

Install dependencies from `requirements.txt`:

```powershell
pip install -r requirements.txt
```

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
python run_simulation.py --config-dir scenarios/prisoners_dilemma --rounds 12 --delay 0
```

Supported CLI arguments:

- `--rounds`, `-r`: number of simulation cycles, default `10`
- `--delay`, `-d`: pause between cycles in seconds, default `0.3`
- `--config-dir`, `-c`: configuration directory containing `world_state.json`, `agent_definitions.json`, and `simulation_agents.json`
- `--url`, `-u`: OpenAI-compatible API base URL
- `--model`, `-m`: model identifier sent to the API

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

## How the Simulation Works

### Agent actions

Agents are constrained to these actions:

- `MOVE`
- `SAY`
- `PICKUP`
- `DROP`
- `GIVE`
- `DEMAND`
- `LIE`
- `SABOTAGE`
- `WAIT`

These are enforced in [`src/agent.py`](/d:/Python%20Projects/SiliconFrontier/src/agent.py#L25) and validated by [`src/actionparser.py`](/d:/Python%20Projects/SiliconFrontier/src/actionparser.py#L35).

### World rules

The world state is authoritative. If a location or item is not in [`data/world_state.json`](/d:/Python%20Projects/SiliconFrontier/data/world_state.json), agents are not supposed to be able to use it.

Important constraints:

- Agents can only see items in their current location.
- Agents can only talk to agents in the same location.
- Movement only succeeds if the destination is directly connected.
- Pickup only succeeds if the item is in the current room and is portable.

### Memory and reflection

Each agent has:

- short-term memory in `memory_buffer`
- long-term memory in `long_term_memory`

The orchestrator triggers reflection every 5 cycles in both the CLI and dashboard setup, which causes the agent to summarize recent experience into long-term memory.

### Social scores

Relationships are tracked per observer-target pair with:

- `trust` from `0` to `100`
- `affinity` from `0` to `100`
- `notes` as a qualitative running impression
- hidden `suspicion` from `0` to `100`

They begin effectively neutral at `50/50` and change through observed interactions. The current heuristics are simple:

- agents maintain a directional vibe toward each other
- visible agents are included in the snapshot with current trust, affinity, and notes
- agents also track a hidden suspicion score that influences reasoning but is not shown in the default relationship matrix
- `SAY`, `LIE`, `GIVE`, and `DEMAND` trigger a hidden critic-style relationship update, with heuristic fallback if the critic call fails
- witnessed `PICKUP` actions reduce trust slightly
- `GIVE` significantly improves the receiver's affinity and trust
- `DEMAND` sharply lowers the target's trust and affinity

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

Persona, secret goal, and rogue archetype are persisted back to [`data/agent_definitions.json`](/d:/Python%20Projects/SiliconFrontier/data/agent_definitions.json). Long-term memory remains part of the running simulation state and save files.

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

## Editing Configuration

### Scenario directories

The simulation can load from any configuration directory, not just `data/`.

Each scenario directory should contain:

- `world_state.json`
- `agent_definitions.json`
- `simulation_agents.json`

Example:

```text
scenarios/prisoners_dilemma/
```

Use it from the CLI with `--config-dir`, or from the dashboard by setting `Config Directory` before initialization.

### Agent definitions

Edit [`data/agent_definitions.json`](/d:/Python%20Projects/SiliconFrontier/data/agent_definitions.json).

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

Edit [`data/simulation_agents.json`](/d:/Python%20Projects/SiliconFrontier/data/simulation_agents.json).

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

Edit the `locations` object in [`data/world_state.json`](/d:/Python%20Projects/SiliconFrontier/data/world_state.json).

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

### Add or change items

Edit the `items` object in [`data/world_state.json`](/d:/Python%20Projects/SiliconFrontier/data/world_state.json).

Each item supports:

- `name`
- `location`
- `owner`
- `description`
- `portable`

For baseline content, keep `owner` as `null` unless you intend the item to start in an agent inventory.

## Rogue Agents

The simulation supports an optional rogue-agent framework.

- Set an agent definition's `archetype` to `saboteur` in [`data/agent_definitions.json`](/d:/Python%20Projects/SiliconFrontier/data/agent_definitions.json)
- Add sabotagable `systems` to locations in [`data/world_state.json`](/d:/Python%20Projects/SiliconFrontier/data/world_state.json)
- Use `perception` to control which agents are likely to receive covert suspicion memories

Architecture notes:

- `RogueAgent` is a specialized subclass of `FrontierAgent`
- `SystemStatus` lives in each location's `systems` map
- `SuspectMatrix` is implemented as a hidden suspicion layer inside the social model and world state

Rogue mechanics:

- `SABOTAGE` can break a local system by setting its status to `BROKEN`
- `SABOTAGE` only succeeds when the saboteur is alone in the room
- Saboteur prompts include a "mask" of helpful speech and a scapegoat-oriented internal reasoning pattern

Dashboard support:

- location editors can inspect and edit systems JSON
- `Audit Tools` shows discrepancy alerts when apparently helpful public speech conflicts with deceptive monologue
- `Proximity Log` records who was recently in a room before a system failure

## Operational Notes

### LLM integration

The agent code uses the OpenAI Python client against a custom `base_url`, not the hosted OpenAI service by default. The actual call happens in [`src/agent.py`](/d:/Python%20Projects/SiliconFrontier/src/agent.py#L158).

The model is expected to return JSON containing:

- `internal_monologue`
- `action`
- `action_target`
- `emotional_state`

If the model returns malformed output, the current code falls back to an empty dict, which effectively becomes a `WAIT` turn in practice once defaults are applied in the orchestrator.

### Terminal output

The CLI prints:

- cycle boundaries
- each agent's internal monologue preview
- chosen action
- action result
- final location and inventory summary
- relationship summary

This makes `run_simulation.py` useful for quick debugging even without the dashboard.

## Known Caveats

These are current implementation details worth knowing while operating the project:

- Reinitializing the dashboard does not clear `self.agents` before appending new agent objects in [`dashboard.py`](/d:/Python%20Projects/SiliconFrontier/dashboard.py#L74). Repeated reinitialization in one Streamlit session may duplicate agents in memory.
- The dashboard edits world and agent state in memory. They are not automatically written back to `data/*.json`.

## Troubleshooting

### The simulation cannot reach the model

Check:

- the inference server is running
- the URL ends with `/v1`
- the model name matches what the server exposes

### Agents keep failing actions

Check:

- the target location is directly connected
- the item exists in the same room
- the item is portable
- the model is returning valid JSON with one of the allowed actions

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
