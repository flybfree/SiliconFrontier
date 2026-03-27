# Silicon Frontier

A local multi-agent LLM simulation. Agents sense their environment, reason internally, take one action per turn, and reflect on outcomes. The simulation runs against any OpenAI-compatible inference server.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Streamlit](https://img.shields.io/badge/UI-Streamlit-red) ![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

Each simulation cycle:

1. An agent receives a filtered view of the world — their location, visible items, nearby agents, and their own memory.
2. The LLM returns internal reasoning, one action, and an emotional state.
3. The action is validated against the world state and executed.
4. Social scores update, memories are written, and witnesses react.

Agents accumulate memory, track goal momentum, and change their behavior based on emotional state, audience, and trust relationships. Two saboteur archetypes and multiple investigator roles are included.

---

## Requirements

- Python 3.10+
- An OpenAI-compatible local or remote inference server (LM Studio, Ollama, vLLM, etc.)

```bash
pip install -r requirements.txt
```

---

## Quick start

### Terminal

```bash
python run_simulation.py --rounds 10 --url http://localhost:1234/v1 --model your-model-name
```

Load a specific scenario:

```bash
python run_simulation.py --config-dir scenarios/cascade_failure --rounds 20 --delay 0
```

### Dashboard

```bash
streamlit run dashboard.py
```

Set the API URL and config directory in the sidebar, click **Initialize Simulation**, then run cycles.

---

## Included scenarios

| Scenario | Agents | Concept |
|---|---|---|
| `data/` (default) | 4 | Station crew with one saboteur and hidden evidence items |
| `scenarios/prisoners_dilemma` | 2 | Two detainees with sealed plea deals and no direct communication |
| `scenarios/cascade_failure` | 8 | Dual saboteurs, 11 locations, 5 hidden forensic evidence items |

Scenarios can also be loaded as dashboard saves from `saves/`.

---

## Agent behavior mechanics

**Inventory** — each agent holds at most two items: one in hand (visible to others) and one concealed on their person (hidden items only).

**Hidden items** — picking up a `hidden: true` item injects its `knowledge` text into the agent's memory and places them under a one-turn drop obligation, forcing them to stay in place.

**Contested items** — `contested: true` items remind agents they are valued resources that others may be competing for.

**Goal momentum** — after every reflection phase, agents assess their own progress as `advancing`, `stalled`, or `setback`. This feeds back into subsequent prompts.

**Emotional state** — a single-word emotional state carries forward turn to turn and colors the agent's reasoning and tone.

**Audience awareness** — agents are told who is watching before each turn, priming divergent public and private behavior.

**Witness reactions** — broadcasts for social actions are emotionally toned per observer based on their current trust and suspicion toward the actor.

**Sabotage alerts** — when a system is sabotaged, all agents on the station receive a notification regardless of location.

---

## Data flow

Each agent turn is a round-trip between the simulation and the LLM.

**1. Sense** — `WorldState.get_snapshot_for_agent()` produces a filtered dict of everything the agent can currently perceive: location, visible items and systems, other agents present (and what they're holding), and relationship scores. `agent.sense()` formats this into a human-readable situation report.

**2. Prompt assembly** — `agent._build_system_prompt()` constructs the system message containing identity, persona, secret goal, inventory, emotional state, long-term memory, goal momentum, audience awareness note, and output format rules. The situation report becomes the user message.

**3. LLM call** — the two-message payload is sent to the OpenAI-compatible endpoint. The model returns JSON:

```json
{
  "internal_monologue": "...",
  "action": "MOVE",
  "action_target": "engineering",
  "emotional_state": "Anxious"
}
```

**4. Validation** — `ActionParser.execute()` checks the action against world state (is the destination adjacent? is the item here? is the hand slot free?) and either executes the mutation or returns a failure.

**5. Memory write** — `agent.interpret_consequence()` turns the result into an experiential sentence appended to the agent's memory buffer. Witnesses in the same room receive a version toned by their trust and suspicion toward the actor.

**6. Reflection** (every 5 cycles) — a second LLM call asks the agent to compress `memory_buffer` into `long_term_memory` and self-assess `goal_momentum`. The buffer is then cleared.

```
WorldState
    │
    ▼
get_snapshot_for_agent()     ← filtered perception
    │
    ▼
agent.sense()                ← situation report  (user message)
_build_system_prompt()       ← identity + rules  (system message)
    │
    ▼
POST /v1/chat/completions    ← LLM call
    │
    ▼
JSON response
    │
    ▼
ActionParser.execute()       ← validates + mutates WorldState
    │
    ▼
interpret_consequence()      ← experiential memory → agent
_broadcast_with_reactions()  ← toned memory → witnesses
    │
    ▼ every 5 cycles
agent.reflect()              ← second LLM call, compresses memory
```

The LLM never touches `WorldState` directly. It only reads a filtered snapshot and returns a structured action. The parser is the only thing that can mutate state.

---

## Project layout

```
run_simulation.py          CLI entry point
dashboard.py               Streamlit dashboard
src/
  agent.py                 Agent cognition, prompting, memory, LLM calls
  orchestrator.py          Simulation loop, event broadcast, reflection
  actionparser.py          Action validation and execution
  worldstate.py            World state storage and snapshot helpers
  socialmatrix.py          Trust, affinity, and suspicion tracking
data/
  world_state.json         Default locations, items, and systems
  agent_definitions.json   Reusable agent definitions
  simulation_agents.json   Active simulation slots
scenarios/
  prisoners_dilemma/       2-agent game theory scenario
  cascade_failure/         8-agent dual-saboteur scenario
saves/                     Dashboard save files
```

---

## Object model

### `FrontierAgent` — [src/agent.py](src/agent.py)

The base agent class. Each instance is one participant in the simulation.

| Method | Purpose |
|---|---|
| `sense(world_snapshot)` | Format the world snapshot into a human-readable situation report (user message) |
| `think_and_act(observation, world_snapshot)` | Assemble the full prompt and call the LLM; returns parsed action JSON |
| `reflect(world_snapshot)` | Second LLM call — compress memory buffer into long-term memory and update goal momentum |
| `interpret_consequence(action, target, success, feedback, nearby_names)` | Turn an action result into an experiential memory sentence |
| `evaluate_social_exchange(...)` | Hidden critic call that returns trust/affinity/suspicion deltas after a social action |
| `add_to_memory(event)` | Append a string to the short-term memory buffer (capped at 10 entries) |

**`RogueAgent`** is a subclass that appends saboteur-specific framing to the system prompt. Instantiated automatically when `archetype == "saboteur"`.

---

### `WorldState` — [src/worldstate.py](src/worldstate.py)

The single source of truth for all simulation state. Nothing exists unless it is in here.

| Method | Purpose |
|---|---|
| `from_json(filepath)` | Load world from a scenario directory's `world_state.json` |
| `to_json(filepath)` | Persist current state to disk |
| `get_snapshot_for_agent(agent_id)` | Return a filtered perception dict for one agent (drives the Sense phase) |
| `get_location(loc_id)` / `add_location(...)` | Read or create a location |
| `get_location_systems(loc_id)` / `set_system_status(loc_id, system_id, status)` | Read or update a system inside a location |
| `is_adjacent(from_loc, to_loc)` | Check whether two locations are connected |
| `get_item(item_id)` / `add_item(...)` | Read or create an item |
| `find_items_by_location(loc_id)` / `find_items_by_owner(agent_id)` | Query items by where they are or who holds them |
| `set_item_hidden(item_id, hidden)` | Toggle concealment flag (used by CONCEAL / PRODUCE actions) |
| `add_item_to_agent_inventory(agent_id, item_id)` | Move item from floor to agent |
| `remove_item_from_agent_inventory(agent_id, item_id)` | Drop item back to agent's current location |
| `transfer_item_between_agents(from_id, to_id, item_id)` | Move item directly between two agents |
| `register_agent(agent_id, location)` | Register a new agent at a starting location |
| `get_agent_location(agent_id)` / `set_agent_location(agent_id, loc_id)` | Read or move an agent |
| `get_visible_agents(agent_id)` | List other agents sharing the same location |
| `get_relationship_view(agent_id, other_id)` / `get_suspicion_view(agent_id, other_id)` | Read social scores between two agents |

---

### `ActionParser` — [src/actionparser.py](src/actionparser.py)

Validates and executes every action the LLM returns. The only code that mutates `WorldState` during a turn.

| Method | Purpose |
|---|---|
| `execute(agent, action_json)` | Route the action to the appropriate handler; return `(success, feedback)` |
| `_handle_move` | Check adjacency, update agent location |
| `_handle_pickup` | Check item presence, portability, and slot availability; transfer to inventory |
| `_handle_drop` | Remove item from inventory, place at current location |
| `_handle_give` / `_handle_demand` | Transfer items between agents with slot enforcement |
| `_handle_say` / `_handle_lie` | Validate non-empty speech; broadcasting is done by the orchestrator |
| `_handle_sabotage` | Saboteur-only; requires solitude; sets system status to `BROKEN` |
| `_handle_repair` | Any agent; sets a `BROKEN` system back to `ONLINE` |
| `_handle_conceal` | Move item from hand slot to concealed person slot |
| `_handle_produce` | Move item from concealed person slot to hand slot |
| `_handle_wait` | No-op; always succeeds |

---

### `Orchestrator` — [src/orchestrator.py](src/orchestrator.py)

Runs the simulation loop and coordinates all subsystems.

| Method | Purpose |
|---|---|
| `run_cycle()` | Execute one full turn for every agent in order; return cycle results |
| `run_simulation(rounds, delay_seconds)` | Run multiple cycles sequentially |
| `broadcast_event(message, location, exclude_agent_id)` | Send an event string to all agents in a location |
| `inject_event(message)` | God Console — push a global memory event to all agents |
| `inject_memory(agent_id, memory_text)` | God Console — append a string directly to one agent's long-term memory |
| `set_agent_location(agent_id, location)` | God Console — teleport an agent |
| `get_event_log()` | Return the full structured event log |
| `get_relationship_snapshot()` | Return current trust/affinity scores across all pairs |

---

### `SocialMatrix` — [src/socialmatrix.py](src/socialmatrix.py)

Tracks directional trust, affinity, and hidden suspicion between every agent pair.

| Method | Purpose |
|---|---|
| `initialize_from_world(world_state)` | Seed matrix from existing relationship data in world state |
| `ensure_agent_network(agent_ids)` | Create neutral entries for any missing pairs |
| `sync_to_world()` | Write current matrix back into `WorldState` |
| `get_scores(agent_a, agent_b)` | Return `(trust, affinity)` from agent_a's perspective |
| `update_scores(agent_a, agent_b, trust_delta, affinity_delta, notes)` | Apply signed deltas to a relationship |
| `set_scores(agent_a, agent_b, trust, affinity, notes)` | Directly set absolute scores |
| `get_suspicion(agent_a, agent_b)` / `update_suspicion(agent_a, agent_b, delta)` | Read or adjust the hidden suspicion score |
| `get_relationship_summary(agent_id)` | All relationships for one agent, sorted by trust |
| `get_trust_network()` | Full network view of trust scores across all agents |

---

## Configuration

The simulation loads from any directory containing three files:

- `world_state.json` — locations, items, sabotagable systems
- `agent_definitions.json` — reusable agent definitions with personas and secret goals
- `simulation_agents.json` — active slots that assign definitions to starting positions

See [USER_MANUAL.md](USER_MANUAL.md) for full configuration reference, item flags, rogue agent setup, and dashboard controls.

---

## Dashboard features

- Run single or batched cycles
- Inspect agent memory, emotional state, and inventory per turn
- Edit agent persona, secret goal, and location live
- Relationship matrix with trust, affinity, and notes per observer-target pair
- World state editor for locations, items, and systems
- God Console for direct intervention (broadcast, memory inject, relocate, persona swap)
- Save and load full simulation state
- Export current state as a reusable scenario directory
