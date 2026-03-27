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

These are enforced in [src/agent.py](src/agent.py) and validated by [src/actionparser.py](src/actionparser.py).

### World rules

The world state is authoritative. If a location or item is not in [data/world_state.json](data/world_state.json), agents are not supposed to be able to use it.

Important constraints:

- Agents can only see items in their current location.
- Agents can only talk to agents in the same location.
- Movement only succeeds if the destination is listed under the current location's `connected_to`. Valid exits are shown explicitly in each agent's situation report.
- Pickup only succeeds if the item is in the current room and is portable.
- Each agent has a two-slot inventory: one item in hand and one concealed on their person. See [Inventory](#inventory) below.

### Inventory

Each agent carries at most two items:

- **In hand**: one regular (non-hidden) item, visible to other agents in the same room.
- **Concealed on person**: one hidden item only.

Rules enforced by the action parser:

- `PICKUP` of any item requires the hand slot to be free.
- `PICKUP` of a hidden item additionally requires the person slot to be free.
- `GIVE` fails if the receiver's hand is already occupied.
- `DEMAND` fails if your own hand is already occupied.

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

They begin effectively neutral at `50/50` and change through observed interactions:

- `SAY`, `LIE`, `GIVE`, and `DEMAND` trigger a hidden critic-style relationship update, with heuristic fallback if the critic call fails
- Witnessed `PICKUP` actions reduce trust slightly
- `GIVE` significantly improves the receiver's affinity and trust
- `DEMAND` sharply lowers the target's trust and affinity

Broadcasts for significant actions (`SAY`, `LIE`, `PICKUP`, `GIVE`, `DEMAND`) are emotionally toned per witness. Each observer receives a version of the event memory coloured by their current trust and suspicion toward the actor. For example, a suspicious witness watching a `PICKUP` gets *"It struck you as opportunistic"* appended to their memory, while a trusting witness sees *"It seemed harmless enough coming from them."*

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

### Add or change items

Edit the `items` object in [data/world_state.json](data/world_state.json).

Each item supports:

- `name`
- `location`
- `owner`
- `description`
- `portable`
- `contested` — optional boolean; marks the item as a valued resource
- `hidden` — optional boolean; enables the knowledge-reveal mechanic on pickup
- `knowledge` — optional string; the information injected into an agent's memory when they pick up a hidden item

For baseline content, keep `owner` as `null` unless you intend the item to start in an agent inventory.

### Hidden items

Setting `hidden: true` on an item activates a risk/reward mechanic:

1. The item appears in the room's visible items list normally. Agents can choose to pick it up.
2. On `PICKUP`, the item's `knowledge` text is injected into the agent's memory as a `[Discovered]` entry.
3. The agent is placed under a **drop obligation**: their next turn's system prompt contains an `URGENT` block instructing them to `DROP` the item immediately. The orchestrator also enforces this mechanically if the LLM ignores the instruction.
4. Once dropped, the obligation clears and the agent is free to act normally.

The risk is that picking up a hidden item consumes the agent's hand slot (requiring them to drop whatever they were holding first) and forces them to remain in the same location for an extra turn — creating a window for witnesses to arrive.

Example:

```json
"station_log_fragment": {
  "name": "Station Log Fragment",
  "location": "command_deck",
  "owner": null,
  "description": "A torn page from the station maintenance log.",
  "portable": true,
  "hidden": true,
  "knowledge": "The log shows that engineering was accessed at 0300 hours by someone whose ID badge was not recorded."
}
```

### Contested items

Setting `contested: true` on an item causes agents to be reminded of its value whenever it is in their view or in their hand:

- *"Contested resource(s) here: repair_manifest. These are valuable and others may seek them."*
- *"You are holding contested resource(s): plasma_wrench. Others may want these."*

This primes competitive reasoning without adding hard game rules.

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
- the agent's hand slot is free before attempting `PICKUP`
- the model is returning valid JSON with one of the allowed actions

### Agents are stuck dropping an item every turn

An agent with `pending_drop` set will be forced to drop a hidden item before doing anything else. If the drop keeps failing (e.g. because the item ID no longer exists in the world state), the obligation cannot clear. Use the God Console to relocate the agent or inject a memory to break the loop, then fix the item data.

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
