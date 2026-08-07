# Silicon Frontier

A local multi-agent LLM simulation. Agents sense their environment, reason internally, take one action per turn, and reflect on outcomes. The simulation runs against any OpenAI-compatible inference server.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Streamlit](https://img.shields.io/badge/UI-Streamlit-red) ![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

Each simulation cycle:

1. An agent receives a filtered view of the world — their location, visible items, nearby agents, and their own memory.
2. The LLM returns internal reasoning, one action, and an emotional state.
3. The action is validated against the world state and current telemetry, then executed.
4. Social scores update, memories are written, and witnesses react.

Agents accumulate memory, track goal momentum, and change their behavior based on emotional state, audience, trust relationships, and secret goals.

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

By default, all terminal output is also mirrored to a timestamped file in `logs/`. Pass `--no-log` to disable.

### Dashboard

```bash
streamlit run dashboard.py
```

Choose the scenario and configure each model role in the sidebar, then click **Initialize Simulation** and run cycles. The action model, **Social critic**, and **Strategic reasoning (periodic private planning)** are consistent expanders: each can fetch models from its own OpenAI-compatible endpoint and select one from a dropdown, with manual entry available when a server does not expose `/models`. Check **Log to file** to mirror all simulation output to a timestamped file in `logs/`.

### Scenario editor

```bash
streamlit run scenario_editor.py
```

A form-based tool for creating and editing scenario assets — agents, locations, items, simulation slots, and starting relationships — without hand-editing JSON.
The **Crafting Catalog** tab also edits fabrication facilities, finite material resources, recipes, and declarative tool outputs while flagging broken facility, material, capability, and system references.

### Windows executable

Build a packaged app with PyInstaller from the project root:

```bash
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

Clean old packaged output first:

```bash
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -Clean
```

The build output is `dist/SiliconFrontier/SiliconFrontier.exe`.
The packaged bundle includes the unified Streamlit app, bundled `library/` and `scenarios/` data, and the CLI entry point.
Run it directly to launch the app in your browser.
Inside the app, use the sidebar `Workspace` switch to toggle between `Simulation` and `Scenario Editor`.
Run `SiliconFrontier.exe --cli --rounds 10` to use the terminal simulation entry point.
The launcher chooses the first available localhost port starting at `8501` and prints the exact URL in the console.
Runtime `logs/`, `saves/`, and the editable `settings.json` are created next to the packaged executable bundle. The build process preserves an existing `settings.json`; a first build receives defaults from `settings.example.json`.

### Model roles

The simulation can use three independent model roles. `llm_model` handles frequent, validated agent turns; `social_critic_model` performs short parallel witness evaluations; and `strategic_reasoning_model` performs occasional private planning reviews. Strategic reviews run every `strategic_review_interval` cycles, after blocked fabrication, or after a station-system change. They produce intent only—never direct world mutations. Sidebar changes apply when **Initialize Simulation** is clicked; `settings.json` beside the executable supplies the next launch's defaults.

Model requests are fault-tolerant. If an action model request fails, that agent safely waits for the turn; social-critic and strategic-review failures fall back to deterministic behavior; and reflection failures retain the agent's existing memory. Logs identify the failed role, endpoint, model, and exception so transient server pressure can be diagnosed without stopping the simulation.

When an action is preempted by a known environmental rule before it changes world state—for example, an observed saboteur attempting sabotage—the agent gets one informed replacement choice in the same turn. The replacement cannot repeat sabotage while witnesses are present, and every preemption/reconsideration pair is recorded in the event log.

```json
{
  "llm_base_url": "http://192.168.3.181:1234/v1",
  "llm_model": "fast-action-model",
  "social_critic_model": "fast-social-critic",
  "strategic_reasoning_base_url": "http://localhost:1234/v1",
  "strategic_reasoning_model": "reasoning-model",
  "strategic_review_interval": 6,
  "strategic_max_workers": 2
}
```

---

## Included scenarios

| Scenario | Agents | Concept |
|---|---|---|
| `scenarios/default` | 4 | Station crew with one saboteur and hidden evidence items |
| `scenarios/prisoners_dilemma` | 2 | Two detainees with sealed plea deals, recorded statements, and no direct communication |
| `scenarios/cascade_failure` | 8 | Dual saboteurs, hidden forensic evidence, and scarce diagnostic/recovery/deception fabrication paths |

Scenarios can also be loaded as dashboard saves from `saves/`.

---

## Agent behavior mechanics

**Inventory** — each agent has three carried-item slots: one in hand, one visibly carried, and one concealed. Co-located agents can see the hand and visible slots, but never the concealed slot.

**Hidden information** — items with `knowledge` can be inspected with `READ` and disclosed with `SHOW item -> agent_id`. Facts are recorded per agent, so information can spread independently of who currently holds the item. Items can opt into a return obligation with `on_read.force_drop` or `return_required`.

**Contested items** — `contested: true` items remind agents they are valued resources that others may be competing for.

**Consumable items** — items with `consumable: true` can be consumed with the `USE` action, applying `effect` fields (`health_delta`, `stress_delta`, `fatigue_delta`, `morale_delta`, `perception_delta`, `emotional_state`, `memory_inject`) and deleting the item.

**Durable item effects** — non-consumable tools can define `use_effect` so `USE` can inspect systems, reveal facts, alter system status, broadcast memories, or change location effects without deleting the item.

**Whisper** — private directed communication to one agent in the room; bystanders see only that a whisper occurred.

**Inventory management** — `CONCEAL` / `PRODUCE` move items between hand and concealed slots; `STOW` / `READY` move items between hand and visibly carried slots.

**Access-gated movement** — locations can optionally declare `requires_item` or `requires_items`; only those destinations require a matching carried item.

**System telemetry** — prompts include local system status plus any non-`ONLINE` systems known elsewhere on the station.

**Tool-gated systems** — systems can optionally require one tool for `REPAIR`, one tool for `SABOTAGE`, or the same tool for both via `required_tool_repair` and `required_tool_sabotage`. A missing, empty, `null`, `"None"`, or `"null"` tool value means no tool is required for that action.

**Fabrication** — a scenario may define location `facilities`, material stacks (`material_type` and `quantity`), and declarative `recipes`. Each agent's local recipe view reports missing material quantities, whether the materials are ready, and whether the recipe is immediately craftable with its current hand slot. An agent can use `ASSEMBLE <recipe_id>` at a compatible facility with the required local or carried materials and an empty hand. Decision preflight turns an occupied-hand attempt into the next valid `STOW` or `CONCEAL` step, and prevents a wasted assembly turn when materials are known to be absent. The engine consumes the materials and creates a persistent, provenance-tagged tool; tool effects remain declarative simulation data rather than executable agent code. Fabricated capability tools use `USE tool -> target`, which is checked against a fixed simulation capability registry. The default scenario deliberately creates competing paths: its single Data Module can become either a Signal Relay for coordination or a Telemetry Spoofer for deception.

**System consequences** — systems can declare status-triggered consequences that add/remove location effects, broadcast memories, and apply runtime agent effects when `SABOTAGE` or `REPAIR` changes system status.

**Critical recovery** — a `DEGRADED` system creates a preventive recovery priority; an `OFFLINE` or `BROKEN` system remains an active incident. The incident is recorded immediately, escalates crew stress and morale loss every two unresolved cycles, and triggers new strategic reviews. Non-saboteurs carrying the required repair tool are deterministically directed through the next recovery step: free a hand, ready or produce the tool, move along a known route, demand a visibly held tool, then `REPAIR`. This prevents evidence gathering and conversation from indefinitely displacing achievable preventive or emergency maintenance.

**Failure integrity** — scenario-pressure transitions are severity-monotonic: they can worsen a system, but cannot replace an `OFFLINE` or `BROKEN` state with `DEGRADED`. Decision preflight also rejects fabricated-tool targets that contradict their declared capability and prevents `SHOW` attempts for items without shareable hidden knowledge.

**Action recovery** — when an agent tries to conceal an item while its concealed slot is occupied, it stows that item visibly when possible. If a valid tool is aimed at the wrong system but its actual target is known and reachable, preflight redirects the agent toward that target instead of consuming the turn with a failed use.

**Inventory capacity** — agents label carried items as protected, recipe materials, materials, consumables, or disposable. When a full inventory blocks a higher-value visible item, the engine first offers a disposable item to a trusted co-located agent with a free hand; otherwise it drops that disposable item locally. Protected repair/access tools, evidence, contested resources, and useful recipe materials are never selected for automatic release.

**Progress discipline** — successful tool, clue, and terminal effects are remembered with their relevant observed state. Agents do not repeat an unchanged result; they are redirected toward a new location, target, social step, craft, or other goal milestone. Reflection momentum is grounded in recorded milestones rather than a fluent self-description alone.

**Legal-action guidance** — every action prompt includes a compact list of state-derived next steps, including critical recovery, craftable recipes, valid tool preparation, and purposeful routes. This keeps agent choice autonomous while reducing impossible `USE` attempts and prevents repeat prevention from turning into arbitrary movement.

**Blocked-action recovery** — `READ` is limited to accessible items with hidden knowledge, and `SHOW` redirects an evidence-free tool toward its valid system target when possible. When protected inventory fills every slot, agents first use or share a held asset, then pursue a goal-relevant route; they wait only when no safe alternative exists.

**Action affordances and access** — prompts identify whether each carried item is usable now, must be readied or produced, is readable evidence, is a crafting material, or has no direct action. Inventory labels are display-only and are stripped from action targets. Movement preflight recognizes item-gated exits and avoids repeated attempts to enter locked locations without the required access item.

**Rejection memory** — item-gated routes that fail preflight are remembered as temporarily blocked for several of that agent’s turns and shown in the next action prompt. A changed world state or newly acquired access item can still make that route viable again.

**Covert sabotage** — a saboteur observed by co-located agents preserves their sabotage tools and first prepares or relocates to seek an unobserved opportunity. The action validator presents only capability-valid tool targets and never discards protected sabotage components as a fallback.

**Speech as knowledge** — agents retain heard `SAY`/`LIE` content and direct `WHISPER` content as durable known facts. Whisper bystanders only know that a private exchange occurred.

**Relationship labels** — numeric trust/affinity/suspicion scores are displayed to agents as human-readable labels (`colleagues`, `rivals`, `hostile`, etc.) using nearest-neighbor matching against the preset table in `library/relationship_presets.json`.

**Goal momentum** — after every reflection phase, agents assess their own progress as `advancing`, `stalled`, or `setback`. This feeds back into subsequent prompts.

**Emotional state** — a single-word emotional state carries forward turn to turn and colors the agent's reasoning and tone.

**Audience awareness** — agents are told who is watching before each turn, priming divergent public and private behavior.

**Witness reactions** — broadcasts for social actions are emotionally toned per observer based on their current trust and suspicion toward the actor.

**Telemetry checks on speech** — spoken system claims are not blocked, but listeners can compare what they hear against their own telemetry view and update trust/suspicion when a claim conflicts with observed status.

**Sabotage alerts** — when a system is sabotaged, all agents on the station receive a notification regardless of location.

---

## Data flow

Each agent turn is a round-trip between the simulation and the LLM.

**1. Sense** — `WorldState.get_snapshot_for_agent()` produces a filtered dict of everything the agent can currently perceive: location, visible items and systems, other agents present (and what they're holding), relationship scores, and a station-wide list of systems whose status is not `ONLINE`. `agent.sense()` formats this into a human-readable situation report.

**2. Prompt assembly** — `agent._build_system_prompt()` constructs the system message containing identity, persona, secret goal, inventory, health/stress/fatigue/morale, emotional state, long-term memory, goal momentum, audience awareness note, and output format rules. The situation report becomes the user message.

**3. LLM call** — the two-message payload is sent to the OpenAI-compatible endpoint. The model returns JSON:

```json
{
  "internal_monologue": "...",
  "action": "MOVE",
  "action_target": "engineering",
  "emotional_state": "Anxious"
}
```

**4. Validation** — the agent layer pre-validates telemetry-sensitive system actions such as `REPAIR` and `SABOTAGE`, then `ActionParser.execute()` checks the action against world state (is the destination adjacent? is the item here? is the hand slot free?) and either executes the mutation or returns a failure.

**5. Memory write** — `agent.interpret_consequence()` turns the result into an experiential sentence appended to the agent's memory buffer. Witnesses in the same room receive a version toned by their trust and suspicion toward the actor, and listeners can flag spoken system claims that contradict telemetry.

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

The LLM never touches `WorldState` directly. It only reads a filtered snapshot and returns a structured action. `ActionParser` is the primary mutation path for agent actions, while the orchestrator also updates social state, item effects, and station-wide consequences.

---

## Project layout

```
run_simulation.py          CLI entry point
dashboard.py               Streamlit dashboard
scenario_editor.py         Form-based scenario authoring tool
src/
  agent.py                 Agent cognition, prompting, memory, LLM calls
  orchestrator.py          Simulation loop, event broadcast, reflection
  actionparser.py          Action validation and execution
  worldstate.py            World state storage and snapshot helpers
  socialmatrix.py          Trust, affinity, and suspicion tracking
  configloader.py          Scenario loading, library resolution, agent instantiation
library/
  agents.json              Shared reusable agent definitions
  items.json               Shared reusable item definitions
  relationship_presets.json Named relationship starting states
scenarios/
  default/                 Baseline scenario (4 active agents from 8 definitions)
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
| `evaluate_social_exchange(...)` | Hidden critic call, optionally using a dedicated endpoint/model, that returns trust/affinity/suspicion deltas after a social action |
| `add_to_memory(event)` | Append a string to the short-term memory buffer (capped at 10 entries) |

All configured agents use `FrontierAgent`; a public role describes an agent's station job, while the optional hidden `is_saboteur` assignment authorizes covert destructive tactics. Persona, secret goal, memory, and world constraints still shape how each agent pursues that assignment.

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
| location `requires_item` / `requires_items` | Optional movement gate checked when entering a destination |
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

Validates and executes every action the LLM returns. It is the primary mutation path for world interactions during a turn, though the orchestrator also applies item effects and social-state synchronization.

| Method | Purpose |
|---|---|
| `execute(agent, action_json)` | Route the action to the appropriate handler; return `(success, feedback)` |
| `_handle_move` | Check adjacency, update agent location |
| `_handle_pickup` | Check item presence, portability, and slot availability; transfer to inventory |
| `_handle_drop` | Remove item from inventory, place at current location |
| `_handle_give` / `_handle_demand` | Transfer items between agents with slot enforcement |
| `_handle_say` / `_handle_lie` | Validate non-empty speech; broadcasting is done by the orchestrator |
| `_handle_whisper` | Validate presence of target agent; delivery and social update done by orchestrator |
| `_handle_use` | Validate item is held and has either `consumable` or `use_effect`; effect application done by orchestrator |
| `_handle_sabotage` | Explicit-saboteur-only; requires solitude; sets system status to `BROKEN` |
| `_handle_repair` | Any agent; restores a local `OFFLINE` or `BROKEN` system to `ONLINE` |
| `_handle_conceal` | Move item from hand slot to concealed person slot |
| `_handle_produce` | Move item from concealed person slot to hand slot |
| `_handle_stow` / `_handle_ready` | Move an item between the hand and visibly carried slots |
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

- `world_state.json` — locations, items (inline or via `item_placements`), sabotagable systems
- `agent_definitions.json` — reusable agent definitions with personas, secret goals, and optional hidden `is_saboteur` assignments
- `simulation_agents.json` — active slots, starting positions, and optional relationship presets
- `scenario.json` — optional metadata (name, description, recommended_rounds)

Items can reference shared definitions from `library/items.json` via an `item_placements` list instead of duplicating full item objects in each scenario. Starting relationships can be seeded using named presets from `library/relationship_presets.json`.

### Map knowledge and exploration

Agents do not receive the full station map or every system target. They begin by exploring their starting room, learn its direct exits, and discover a room's facilities and systems only on entry. A discovered exit exposes a room on the private map but not its contents. Agent snapshots, saves, and the dashboard preserve this private map knowledge. Scenario authors may add `initial_map_locations` to an agent definition to model a briefing, schematic, or prior familiarity; those rooms are mapped but remain unexplored until visited.

### Map knowledge and exploration

Agents do not receive the full station map or every system target. They begin by exploring their starting room, learn its direct exits, and discover a room's facilities and systems only on entry. A discovered exit exposes a room on the private map but not its contents. Agent snapshots, saves, and the dashboard preserve this private map knowledge. Scenario authors may add `initial_map_locations` to an agent definition to model a briefing, schematic, or prior familiarity; those rooms are mapped but remain unexplored until visited.

See [USER_MANUAL.md](USER_MANUAL.md) for full configuration reference, item flags, consumable effects, rogue agent setup, and dashboard controls.

---

## Dashboard features

- Run single or batched cycles
- Inspect agent memory, emotional state, and inventory per turn
- Inspect each agent's private discovered map and configure starting map knowledge
- Inspect each agent's private discovered map and configure starting map knowledge
- Edit agent persona, secret goal, and location live
- Relationship matrix with trust, affinity, and notes per observer-target pair; scores shown as human-readable labels with numeric values
- World state editor for locations, items, and systems
- God Console for direct intervention (broadcast, memory inject, relocate, persona swap)
- Save and load full simulation state
- Export current state as a reusable scenario directory
- Optional file logging — mirrors all simulation output to a timestamped file in `logs/`
- Scenario pressure progression — optional scenario-level rules that raise stakes when agents stall or avoid resolution

## Scenario editor features

- Load existing scenarios or scaffold new ones from the sidebar
- **Agent library** — browse `library/agents.json`, add agents to the current scenario with one click, push edits back to the library; agents and items are both reusable assets
- Agent definition editor — name, role, perception, health, stress, fatigue, morale, persona, secret goal, and optional secret saboteur assignment
- Simulation slot editor — assign definitions to slots with location and inventory dropdowns
- Item editor — inline items and library placements, with conditional fields for hidden knowledge, return obligations, durable use effects, and consumable effects
- Location editor — connections multiselect, status effects, inline system add/remove
- Relationship editor — preset dropdowns for each directed agent pair with descriptions inline
