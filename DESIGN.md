Design Document: The Silicon Frontier Framework

This document describes the framework as it is currently implemented.

## 1. System Architecture

Silicon Frontier is a stateful simulation loop around an OpenAI-compatible chat model.

Major layers:

- **Inference layer**: `OpenAI` Python client configured with a custom `base_url`
- **State layer**: `WorldState` stores locations, items, agents, relationships, and suspicions
- **Decision layer**: `FrontierAgent` converts filtered state into prompt text and returns one action
- **Rule layer**: `ActionParser` validates and executes deterministic mutations
- **Temporal layer**: `Orchestrator` runs turns, broadcasts consequences, and triggers reflection
- **Observation / editing layer**: `dashboard.py` and `scenario_editor.py`

The key implementation principle is still strict separation between:

- model-generated intent
- code-enforced outcome

## 2. World Model

The station world is defined by JSON-backed nested dictionaries.

Implemented entities:

- **Locations**: IDs mapped to `name`, `description`, `connected_to`, `status_effects`, and `systems`
- **Systems**: per-location maps containing status-bearing station infrastructure such as consoles, generators, and reactor controls
- **Items**: movable or static objects with flags such as `portable`, `hidden`, `contested`, `consumable`, and optional `effect`
- **Agents**: runtime entities with a location, inventory, and status effects
- **Relationships / Suspicions**: directional social state visible or hidden depending on use

The world state is the only source of truth. The model never mutates it directly.

## 3. Agent Cognitive Loop

Each agent follows a `Sense -> Think -> Act -> Reflect` cycle.

### Sense

`WorldState.get_snapshot_for_agent()` provides a filtered snapshot containing:

- current location
- visible items
- visible local systems
- visible nearby agents and their visible hand items
- directional relationship impressions
- the agent's own inventory
- `abnormal_systems`: station-wide systems whose status is not `ONLINE`

`FrontierAgent.sense()` turns that snapshot into human-readable prompt text.

Current implementation detail:

- the situation report explicitly tells the model that listed telemetry is authoritative for the turn

### Think / Act

`FrontierAgent._build_system_prompt()` builds a system prompt containing:

- identity and role
- persona and secret goal
- visible inventory state
- emotional state
- nearby social context
- local systems
- station-wide known non-`ONLINE` systems
- action-format rules
- telemetry-grounding rules
- long-term memory and goal momentum

`think_and_act()` sends the system prompt plus the situation report to the configured chat backend.

The expected response shape is JSON with:

- `internal_monologue`
- `action`
- `action_target`
- `emotional_state`

Structured-output mode exists but is optional and backend-dependent.

### Post-generation validation

After parsing, the agent normalizes the response into a safe decision payload.

Current implementation validates telemetry-sensitive system actions before parser execution:

- `REPAIR` is downgraded to `WAIT` if the local target is not visible or not `OFFLINE` / `BROKEN`
- `SABOTAGE` is downgraded to `WAIT` if the local target is not visible or is already `BROKEN`

Speech is intentionally not rewritten:

- `SAY`
- `LIE`
- `WHISPER`

This preserves deception, bluffing, and confusion as social behavior.

### Reflect

Every `reflection_interval` cycles, `FrontierAgent.reflect()` performs a second model call that compresses:

- recent short-term memory
- recent social changes
- perceived progress toward the secret goal

The agent updates:

- `long_term_memory`
- `goal_momentum`

## 4. Deterministic Action Enforcement

`ActionParser` is the hard rule boundary.

Implemented action families include:

- navigation: `MOVE`
- social speech: `SAY`, `WHISPER`, `LIE`
- inventory transfer: `PICKUP`, `DROP`, `GIVE`, `DEMAND`
- slot management: `CONCEAL`, `PRODUCE`
- item effects: `USE`
- system actions: `REPAIR`, `SABOTAGE`
- no-op: `WAIT`

Examples of enforced constraints:

- moves must target adjacent locations
- items must exist where claimed
- inventory slot rules must hold
- `WHISPER` requires a valid `message -> agent_id` target and a present recipient
- `SABOTAGE` requires the saboteur archetype and no witnesses in the room
- `REPAIR` requires a valid local broken/offline target and may require a specific tool

The parser remains authoritative even when the agent layer has already prevalidated part of the decision.

## 5. Social Dynamics

The framework tracks more than trust/affinity now.

Implemented social state:

- `trust`
- `affinity`
- hidden `suspicion`
- free-text `notes`

These values are directional. One agent's view of another can differ from the reverse direction.

Relationship updates come from:

- a hidden critic model call via `FrontierAgent.evaluate_social_exchange()`
- heuristic fallback when that call fails
- direct rule-based updates from witnessed actions
- covert witness logic for sabotage
- listener-side telemetry contradiction checks on speech

## 6. Speech, Deception, and Telemetry

This is the main area where the implementation has evolved beyond the original design.

### Telemetry in prompts

Agents are prompted with:

- local visible systems and statuses
- station-wide non-`ONLINE` systems and their locations

The prompt instructs the model to treat listed telemetry as authoritative.

### Telemetry in actions

Telemetry is used to constrain system mutations:

- invalid `REPAIR` / `SABOTAGE` actions are downgraded before parser execution

### Telemetry in social interpretation

Speech is still allowed to be false.

When another agent hears:

- a room-level `SAY`
- a room-level `LIE`
- a direct `WHISPER`

the listener can compare the spoken claim against their own telemetry snapshot. If a contradiction is detected:

- the listener receives a `[Telemetry check]` memory
- the speaker loses trust with that listener
- the speaker gains suspicion from that listener

This preserves social deception while keeping world mutation grounded.

## 7. Orchestration and Causality

`Orchestrator` manages causal ordering.

Implemented per-turn behavior:

1. increment cycle count
2. record a room-occupancy snapshot for later incident audits
3. print a station-wide system status snapshot to the console at the start of each agent turn
4. build the acting agent's snapshot and prompt
5. request one decision from the model
6. enforce pending hidden-item drop obligations
7. execute the action through `ActionParser`
8. write consequence memory to the actor
9. broadcast witnessed consequences to others
10. update trust / affinity / suspicion where applicable
11. record event log entries
12. run reflection when the interval is reached

Additional orchestrator responsibilities:

- station-wide sabotage and repair announcements
- sabotage incident logging with prior room occupancy
- covert high-perception witness memory injection for sabotage
- telemetry-based speech contradiction checks

## 8. Experimental Controls

The current codebase still supports guided intervention and observation through the dashboard.

Available controls include:

- global event injection
- direct memory injection
- relocating agents
- editing live world state
- editing systems in locations
- monitoring long-term and short-term memory
- inspecting trust, affinity, and suspicion

This makes the framework useful both as a sandbox and as a reproducible experiment environment.

## 9. What Changed Relative to the Original Design

The current implementation differs from the older conceptual docs in several important ways:

- the action set is much larger than `MOVE`, `SAY`, `PICKUP`, `DROP`, `WAIT`
- agents track `emotional_state`, `goal_momentum`, `pending_drop`, and hidden suspicion
- prompt input includes relationship labels, visible hand items, and telemetry summaries
- there is explicit telemetry-aware validation before parser execution
- speech can be socially checked against telemetry by listeners
- the orchestrator prints system snapshots and tracks sabotage incidents / proximity logs
- social consequences are partly LLM-critic-driven and partly rule-driven

## 10. Replication Notes

To reproduce current behavior:

1. Run an OpenAI-compatible chat endpoint.
2. Load a scenario containing `world_state.json`, `agent_definitions.json`, and `simulation_agents.json`.
3. Initialize agents through `configloader.py`.
4. Run cycles through `Orchestrator`.
5. Observe:
   - event log
   - console status snapshots
   - trust / affinity / suspicion changes
   - memory buffers
   - reflection outputs

For telemetry/deception experiments, use a scenario with systems and at least one agent likely to make or hear claims about station status.
