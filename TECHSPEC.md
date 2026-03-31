Part II: Technical Specifications & Object Model

This document reflects the current implementation in `src/`, not the original design intent.

## 1. FrontierAgent Object

`FrontierAgent` in [src/agent.py](src/agent.py) is the primary cognitive unit.

Key attributes:

- `agent_id`, `name`: runtime identity used in logs, world state, and social updates
- `persona`, `secret_goal`, `role`, `archetype`: prompt anchors and behavior framing
- `perception`: integer `[0, 100]`; currently used for covert suspicion witness logic in the orchestrator
- `memory_buffer`: short-term event list; the agent sees the last 5 entries in `sense()`
- `long_term_memory`: persistent summary generated during reflection
- `goal_momentum`: one of `advancing`, `stalled`, `setback`
- `emotional_state`: carried turn to turn and injected into the prompt
- `pending_drop`, `pending_drop_name`: hidden-item obligation state
- `last_structured_output_status`: reports whether the turn used structured output, fallback parsing, or telemetry correction

Primary responsibilities:

- Convert a filtered world snapshot into a subjective text situation report with `sense()`
- Build the turn system prompt with `_build_system_prompt()`
- Call an OpenAI-compatible chat endpoint in `think_and_act()`
- Normalize model output into a safe decision shape
- Pre-validate telemetry-sensitive system actions before parser execution
- Evaluate heard social actions with `evaluate_social_exchange()`
- Reflect short-term memory into long-term memory with `reflect()`

Current prompt behavior:

- Agents are shown local visible systems plus a station-wide list of systems whose status is not `ONLINE`
- Prompt rules explicitly tell the model to treat listed telemetry as authoritative
- The prompt still allows deceptive or mistaken speech; only system actions are pre-corrected

Telemetry-aware validation inside `FrontierAgent`:

- `REPAIR` is downgraded to `WAIT` unless the targeted visible local system exists and is `OFFLINE` or `BROKEN`
- `SABOTAGE` is downgraded to `WAIT` unless the targeted visible local system exists and is not already `BROKEN`
- `SAY`, `LIE`, and `WHISPER` are not rewritten by telemetry validation
- `assess_message_against_telemetry()` lets a listener judge spoken system claims against their own snapshot

## 2. WorldState Schema

`WorldState` in [src/worldstate.py](src/worldstate.py) is the authoritative ground truth.

Core top-level maps:

- `locations`
- `items`
- `agents`
- `relationships`
- `suspicions`

Location structure:

- `name`
- `description`
- `connected_to`
- `status_effects`
- `systems`

System entries live inside each location's `systems` map. A system entry may include:

- `name`
- `status`
- `description`
- `required_tool`

Item state includes:

- room or owner placement
- `portable`
- `hidden`
- `contested`
- `knowledge`
- `consumable`
- `effect`

Agent runtime state tracked by the world:

- `location`
- `inventory`
- `status_effects`

Snapshot behavior:

`get_snapshot_for_agent(agent_id)` returns a filtered dict containing:

- `current_location`
- `visible_items`
- `visible_systems`
- `abnormal_systems`: all systems anywhere in the station whose status is not `ONLINE`
- `visible_agents`
- `visible_agent_hands`
- `relationship_impressions`
- `agent_inventory`

This snapshot is what the agent prompt is built from. The model never receives the full raw world state.

## 3. ActionParser

`ActionParser` in [src/actionparser.py](src/actionparser.py) is the deterministic action arbiter.

It validates and executes all world mutations, including:

- movement adjacency
- item pickup/drop/inventory-slot constraints
- give/demand transfer rules
- whisper target presence
- sabotage solitude requirement
- repair status and required-tool requirements
- conceal/produce slot management
- item consumption

Important implementation detail:

- Some validation is split across layers.
- `FrontierAgent` pre-validates telemetry-sensitive system actions before execution.
- `ActionParser` still performs authoritative state checks during execution.

Current system-action rules in the parser:

- `SABOTAGE` is saboteur-only
- `SABOTAGE` fails if another visible agent is present
- `SABOTAGE` fails if the local target system is already `BROKEN`
- `REPAIR` only succeeds on a local target system whose status is `OFFLINE` or `BROKEN`
- `REPAIR` can require a named tool in the actor's visible hand slot

## 4. Orchestrator

`Orchestrator` in [src/orchestrator.py](src/orchestrator.py) manages turn order, observation, and cross-agent consequences.

Current responsibilities:

- initialize and synchronize the `SocialMatrix`
- run cycles in fixed order
- print a full station system-status snapshot at the start of every agent turn
- request each agent's decision
- enforce hidden-item drop obligations
- execute actions through `ActionParser`
- append experiential memories to the actor
- broadcast witnessed events
- apply relationship and suspicion updates
- maintain event, proximity, and system-incident logs
- trigger periodic reflection

Speech handling:

- `SAY` and `LIE` are broadcast to every witness in the room with relationship-toned memory text
- `WHISPER` is delivered only to the named target; bystanders only learn that a whisper occurred
- listeners can compare received speech against their own telemetry via `_apply_telemetry_speech_check()`
- when a contradiction is detected, the listener receives a `[Telemetry check]` memory and the speaker loses trust / gains suspicion from that listener

System-event handling:

- successful `REPAIR` triggers a station-wide restoration announcement
- successful `SABOTAGE` triggers a station-wide failure alert
- sabotage incidents are recorded with recent room occupancy
- high-perception co-located witnesses may receive covert sabotage memories and hidden suspicion updates

## 5. SocialMatrix

`SocialMatrix` in [src/socialmatrix.py](src/socialmatrix.py) tracks directional social state.

Tracked values:

- `trust`
- `affinity`
- hidden `suspicion`
- free-text `notes`

Properties of the implementation:

- social state is directional, not symmetric
- the matrix is initialized from world-state relationship data
- `ensure_agent_network()` backfills neutral links for missing pairs
- `sync_to_world()` keeps the world-state relationship layer aligned with the matrix

Update sources:

- social critic output from `FrontierAgent.evaluate_social_exchange()`
- heuristic fallback in the orchestrator when critic output is unavailable
- witnessed pickups, repairs, demands, sabotage evidence, and telemetry-conflict speech checks

## 6. Structured Output and Fallbacks

Turn generation supports optional structured-output mode in `FrontierAgent`.

Observed statuses include:

- `structured_ok`
- `structured_fallback`
- `structured_parse_fallback`
- `structured_disabled`
- `structured_validated`
- `structured_validated_corrected`

Behavior:

- if structured schema mode is enabled and supported, the agent requests strict JSON
- if the backend rejects schema mode, the agent falls back to plain chat completion
- if parsing fails after a structured response, a non-schema retry is attempted
- any returned decision is normalized into a safe shape before telemetry-sensitive validation runs

## 7. Runtime Data Flow

Per agent turn:

1. `WorldState.get_snapshot_for_agent()` builds the filtered snapshot
2. `Orchestrator` prints the full station status snapshot to the console log
3. `FrontierAgent.sense()` formats the subjective situation report
4. `FrontierAgent._build_system_prompt()` assembles prompt rules and identity state
5. `FrontierAgent.think_and_act()` calls the LLM and normalizes the decision
6. `FrontierAgent._validate_decision_against_telemetry()` may downgrade invalid `REPAIR` or `SABOTAGE` to `WAIT`
7. `ActionParser.execute()` performs authoritative state mutation or returns failure
8. `Orchestrator` writes actor memory, broadcasts the event, updates social state, and logs the result
9. Every `reflection_interval` cycles, `FrontierAgent.reflect()` condenses memory and updates `goal_momentum`

## 8. Integration Map

| Object | Input | Output | Current Functional Role |
|---|---|---|---|
| `FrontierAgent` | filtered world snapshot, prompt rules, memory | normalized decision JSON | reasoning, action selection, social interpretation |
| `WorldState` | parser/orchestrator updates | filtered snapshots and authoritative truth | state storage and visibility filtering |
| `ActionParser` | normalized action JSON | success flag + feedback + world mutation | deterministic rules enforcement |
| `Orchestrator` | agents, world, parser, social matrix | event log, broadcasts, reflection timing | causal ordering and cross-agent consequences |
| `SocialMatrix` | relationship deltas | directional trust/affinity/suspicion state | persistent social memory |
