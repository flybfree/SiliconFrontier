# Graph Report - SiliconFrontier  (2026-04-26)

## Corpus Check
- 14 files · ~35,111 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 441 nodes · 1059 edges · 24 communities detected
- Extraction: 60% EXTRACTED · 40% INFERRED · 0% AMBIGUOUS · INFERRED: 424 edges (avg confidence: 0.62)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]

## God Nodes (most connected - your core abstractions)
1. `WorldState` - 93 edges
2. `ActionParser` - 65 edges
3. `Orchestrator` - 63 edges
4. `FrontierAgent` - 61 edges
5. `SocialMatrix` - 56 edges
6. `RogueAgent` - 42 edges
7. `main()` - 32 edges
8. `SimulationState` - 27 edges
9. `items()` - 21 edges
10. `_Tee` - 14 edges

## Surprising Connections (you probably didn't know these)
- `ActionParser - The System Arbiter of Silicon Frontier  Validates and executes ag` --uses--> `WorldState`  [INFERRED]
  src\actionparser.py → src\worldstate.py
- `Validate and execute an agent's action.          Args:             agent: Fronti` --uses--> `WorldState`  [INFERRED]
  src\actionparser.py → src\worldstate.py
- `Return the agent's non-hidden (in-hand) inventory items.` --uses--> `WorldState`  [INFERRED]
  src\actionparser.py → src\worldstate.py
- `Return the agent's hidden (on-person) inventory items.` --uses--> `WorldState`  [INFERRED]
  src\actionparser.py → src\worldstate.py
- `Return the configured required tool for a system action.` --uses--> `WorldState`  [INFERRED]
  src\actionparser.py → src\worldstate.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (41): Handle PICKUP action., Validate and execute an agent's action.          Args:             agent: Fronti, validate_pickup(), Build an experiential memory string from an action outcome.          Richer than, Add an event to the short-term memory buffer (max 10 events)., Update the agent's current emotional state., Store a sabotage incident with recent room occupancy context., Print the current status of every system in the station. (+33 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (60): ActionParser, Validates agent actions against world physics and updates state accordingly., Parse an action target into (item, agent_id)., Initialize the action parser with a reference to the world state.          Args:, Handle LIE action as a flagged speech act., Pre-validate a MOVE action without executing., Pre-validate a PICKUP action without executing., Handle SAY action - returns success but actual broadcasting is done by Orchestra (+52 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (24): data_path(), Persist reusable agent definitions., Persist active simulation slots., Persist world_state.json for a scenario/config directory., save_agent_definitions(), save_simulation_slots(), save_world_state(), list_saves() (+16 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (23): _error_suggests_unsupported_schema(), _extract_message_text(), _hand_items_from_snapshot(), FrontierAgent - The Cognitive Unit of Silicon Frontier  Represents an autonomous, Generate a subjective view of the world for the agent.          This filters the, Construct the master system prompt for this agent., Use the local model as a hidden critic for relationship updates., Return a safe decision payload that conforms to the expected schema. (+15 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (38): _active_slot_def_ids(), _agent_fields(), _agent_library(), _all_item_ids(), _create_new_scenario(), _definition_map(), _definition_name(), _definition_options() (+30 more)

### Community 5 - "Community 5"
Cohesion: 0.1
Nodes (28): build_agent_instances(), load_agent_configuration(), load_agent_library(), load_item_library(), _load_json(), load_relationship_presets(), load_scenario_manifest(), Configuration helpers for reusable agent definitions and active simulation slots (+20 more)

### Community 6 - "Community 6"
Cohesion: 0.1
Nodes (14): _parse_social_target(), Return the agent's non-hidden (in-hand) inventory items., Return the agent's hidden (on-person) inventory items., Handle USE action — consume a held item and trigger its effect., Resolve a target agent only if they are currently visible., Handle GIVE action: GIVE item -> agent_id., Handle DEMAND action: DEMAND item -> agent_id., Handle WHISPER action: WHISPER message -> agent_id. (+6 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (9): ActionParser - The System Arbiter of Silicon Frontier  Validates and executes ag, validate_move(), _extract_social_target(), Orchestrator - The Temporal Controller of Silicon Frontier  Manages the simulati, SocialMatrix - The Relational Database of Silicon Frontier  Tracks interpersonal, from_json(), WorldState - The Physics Engine of Silicon Frontier  Provides the "Ground Truth", Get location details by ID. (+1 more)

### Community 8 - "Community 8"
Cohesion: 0.14
Nodes (8): Run the full simulation for a specified number of rounds.          Args:, Get current relationship scores., run_demo_simulation(), run_quick_test(), _start_logging(), _stop_logging(), _Tee, Get all relationships in the matrix.

### Community 9 - "Community 9"
Cohesion: 0.24
Nodes (13): bundle_root(), ensure_runtime_dirs(), is_frozen(), Helpers for locating bundled resources and writable runtime directories., Directory containing packaged resources., Directory the user interacts with at runtime., resource_path(), runtime_root() (+5 more)

### Community 10 - "Community 10"
Cohesion: 0.23
Nodes (6): Return the configured required tool for a system action., Check whether the agent is visibly holding the required tool., Handle SABOTAGE action on a local system., Handle REPAIR action on a local system that is down., Get the system map for a location., Update a named system in a location.

### Community 11 - "Community 11"
Cohesion: 0.33
Nodes (2): Test: agent SABOTAGE and REPAIR actions for system status changes.  Test 1 — no, StubAgent

### Community 12 - "Community 12"
Cohesion: 0.33
Nodes (3): Initialize the orchestrator.          Args:             agents: List of Frontier, Populate relationships from world state data., Mirror the active relationship matrix back into the world state.

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): Return the name of the closest relationship preset for these values.

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): Split a whisper target into message and recipient when present.

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): Return normalized names that may be used to refer to a system.

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): Return the required tool for a system action, if configured.

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): Return visible in-hand items from the snapshot inventory.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): Heuristic for servers that reject structured-output fields.

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): Best-effort extraction of text content from OpenAI-compatible responses.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): Return an emotional tag to append to a witness memory, based on relationship sta

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): Parse an action target into (item_or_message, target_agent_id).

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Load relationships from JSON string.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Load world state from a JSON file.

## Knowledge Gaps
- **126 isolated node(s):** `Return selectable tool/item IDs for system requirements.`, `Return a friendly label for a tool dropdown option.`, `Render the common agent fields and return a dict of current widget values.`, `Render consumable effect sub-fields; return the current dict of values.`, `Windows launcher used for packaged builds.` (+121 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 11`** (6 nodes): `check()`, `_hand_items()`, `test_system_status.py`, `Test: agent SABOTAGE and REPAIR actions for system status changes.  Test 1 — no`, `StubAgent`, `.__init__()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (1 nodes): `Return the name of the closest relationship preset for these values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `Split a whisper target into message and recipient when present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `Return normalized names that may be used to refer to a system.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `Return the required tool for a system action, if configured.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `Return visible in-hand items from the snapshot inventory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Heuristic for servers that reject structured-output fields.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `Best-effort extraction of text content from OpenAI-compatible responses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `Return an emotional tag to append to a witness memory, based on relationship sta`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `Parse an action target into (item_or_message, target_agent_id).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Load relationships from JSON string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Load world state from a JSON file.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `WorldState` connect `Community 1` to `Community 0`, `Community 2`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 11`?**
  _High betweenness centrality (0.275) - this node is a cross-community bridge._
- **Why does `FrontierAgent` connect `Community 1` to `Community 0`, `Community 8`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.155) - this node is a cross-community bridge._
- **Why does `items()` connect `Community 4` to `Community 0`, `Community 2`, `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 10`?**
  _High betweenness centrality (0.146) - this node is a cross-community bridge._
- **Are the 66 inferred relationships involving `WorldState` (e.g. with `_Tee` and `SimulationState`) actually correct?**
  _`WorldState` has 66 INFERRED edges - model-reasoned connections that need verification._
- **Are the 42 inferred relationships involving `ActionParser` (e.g. with `_Tee` and `SimulationState`) actually correct?**
  _`ActionParser` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `Orchestrator` (e.g. with `_Tee` and `SimulationState`) actually correct?**
  _`Orchestrator` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `FrontierAgent` (e.g. with `_Tee` and `SimulationState`) actually correct?**
  _`FrontierAgent` has 37 INFERRED edges - model-reasoned connections that need verification._