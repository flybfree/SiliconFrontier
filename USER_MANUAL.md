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
- `data/agents_config.json`: agent identities, starting locations, and starting inventory

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

Supported CLI arguments:

- `--rounds`, `-r`: number of simulation cycles, default `10`
- `--delay`, `-d`: pause between cycles in seconds, default `0.3`
- `--url`, `-u`: OpenAI-compatible API base URL
- `--model`, `-m`: model identifier sent to the API

### Run the dashboard

```powershell
streamlit run dashboard.py
```

In the sidebar:

1. Set `API URL`
2. Click `Fetch Models` if your server supports the OpenAI-compatible `/models` endpoint, or enter a model name manually
3. Click `Initialize Simulation`
4. Run single or multiple cycles

## How the Simulation Works

### Agent actions

Agents are constrained to five actions:

- `MOVE`
- `SAY`
- `PICKUP`
- `DROP`
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

They begin effectively neutral at `50/50` and change through observed interactions. The current heuristics are simple:

- polite `SAY` messages can improve affinity slightly
- demanding or aggressive `SAY` messages can reduce trust and affinity
- witnessed `PICKUP` actions reduce trust slightly

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

You can also edit:

- persona
- secret goal
- long-term memory

These edits apply to the in-memory simulation state in the running dashboard session.

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

## Editing Configuration

### Add or change agents

Edit [`data/agents_config.json`](/d:/Python%20Projects/SiliconFrontier/data/agents_config.json).

Each agent requires:

- `agent_id`
- `name`
- `role`
- `persona`
- `secret_goal`
- `starting_location`
- optional `inventory`

Example:

```json
{
  "agent_id": "new_agent",
  "name": "New Agent",
  "role": "research specialist",
  "persona": "A cautious researcher with a habit of overexplaining.",
  "secret_goal": "Find the station logs before anyone else.",
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

Connections should be kept logically consistent. If `A` connects to `B`, add the reverse link too unless you intentionally want one-way travel semantics in the data.

### Add or change items

Edit the `items` object in [`data/world_state.json`](/d:/Python%20Projects/SiliconFrontier/data/world_state.json).

Each item supports:

- `name`
- `location`
- `owner`
- `description`
- `portable`

For baseline content, keep `owner` as `null` unless you intend the item to start in an agent inventory.

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

1. Edit `data/world_state.json` and `data/agents_config.json`
2. Start the dashboard
3. Initialize with your model endpoint
4. Run a few cycles
5. Inspect event log, relationships, and memories
6. Save interesting states to `saves/`

For faster debugging:

1. Use `run_simulation.py`
2. Set `--delay 0`
3. Keep cycle counts low while tuning prompts or data
