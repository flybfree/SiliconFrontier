# Graph Report - .  (2026-04-26)

## Corpus Check
- Corpus is ~35,889 words - fits in a single context window. You may not need a graph.

## Summary
- 516 nodes · 1177 edges · 20 communities detected
- Extraction: 61% EXTRACTED · 39% INFERRED · 0% AMBIGUOUS · INFERRED: 463 edges (avg confidence: 0.64)
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
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]

## God Nodes (most connected - your core abstractions)
1. `WorldState` - 98 edges
2. `ActionParser` - 69 edges
3. `Orchestrator` - 63 edges
4. `FrontierAgent` - 61 edges
5. `SocialMatrix` - 56 edges
6. `RogueAgent` - 42 edges
7. `main()` - 32 edges
8. `SimulationState` - 27 edges
9. `items()` - 21 edges
10. `_Tee` - 14 edges

## Surprising Connections (you probably didn't know these)
- `JSON World Structure` --semantically_similar_to--> `WorldState as Source of Truth`  [INFERRED] [semantically similar]
  worldstate.md → DESIGN.md
- `Turn-Based Demo Loop` --semantically_similar_to--> `Orchestrator Temporal Layer`  [INFERRED] [semantically similar]
  orchestrator.md → DESIGN.md
- `Prompt Injection Versus Logic` --semantically_similar_to--> `Model Intent and Code Outcome Separation`  [INFERRED] [semantically similar]
  socialpresence.md → DESIGN.md
- `Runtime Data Flow` --semantically_similar_to--> `Sense Think Act Reflect Cycle`  [INFERRED] [semantically similar]
  TECHSPEC.md → DESIGN.md
- `Validate and execute an agent's action.          Args:             agent: Fronti` --uses--> `WorldState`  [INFERRED]
  D:\Python Projects\SiliconFrontier\src\actionparser.py → D:\Python Projects\SiliconFrontier\src\worldstate.py

## Hyperedges (group relationships)
- **Core Simulation Control Loop** — design_worldstate_source_of_truth, design_frontieragent_decision_layer, design_actionparser_rule_boundary, design_orchestrator_temporal_layer, design_intent_outcome_separation [EXTRACTED 0.95]
- **Social Deception and Witnessing System** — design_speech_deception_preservation, design_telemetry_speech_contradiction_checks, design_directional_social_state, design_hidden_suspicion, readme_witness_reactions, readme_audience_awareness [INFERRED 0.86]
- **Prisoner's Dilemma Mechanics Mapping** — pd_isolated_detainees_uncertainty, pd_payoff_broadcast_protocol, pd_social_actions_as_game_moves, pd_trust_suspicion_self_interest, relationships_social_lab_scenarios [EXTRACTED 0.88]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (59): ActionParser, _parse_social_target(), ActionParser - The System Arbiter of Silicon Frontier  Validates and executes ag, Handle SAY action - returns success but actual broadcasting is done by Orchestra, Return the agent's non-hidden (in-hand) inventory items., Return the agent's hidden (on-person) inventory items., Return the configured required tool for a system action., Check whether the agent is visibly holding the required tool. (+51 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (60): Specialized adversarial agent with saboteur framing., RogueAgent, data_path(), list_saves(), main(), process_queued_cycles(), Manages simulation state across Streamlit sessions., Persist selected definition fields back to the reusable agent catalog. (+52 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (35): Validate and execute an agent's action.          Args:             agent: Fronti, Build an experiential memory string from an action outcome.          Richer than, Add an event to the short-term memory buffer (max 10 events)., Update the agent's current emotional state., Store a sabotage incident with recent room occupancy context., Print the current status of every system in the station., High-perception witnesses can receive covert suspicion memories., Broadcast an action to all witnesses in a location, appending an         emotion (+27 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (63): ActionParser Rule Boundary, Dashboard Experiment Controls, Directional Social State, Filtered Agent Snapshot, FrontierAgent Decision Layer, Hidden Critic Social Update, Hidden Suspicion, Model Intent and Code Outcome Separation (+55 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (26): _error_suggests_unsupported_schema(), _extract_message_text(), FrontierAgent, _hand_items_from_snapshot(), FrontierAgent - The Cognitive Unit of Silicon Frontier  Represents an autonomous, Generate a subjective view of the world for the agent.          This filters the, An autonomous agent with personality, memory, and goal-directed behavior.      E, Construct the master system prompt for this agent. (+18 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (38): build_agent_instances(), load_agent_configuration(), load_agent_library(), load_item_library(), _load_json(), load_relationship_presets(), load_scenario_manifest(), Configuration helpers for reusable agent definitions and active simulation slots (+30 more)

### Community 6 - "Community 6"
Cohesion: 0.13
Nodes (39): _active_slot_def_ids(), _agent_fields(), _agent_library(), _all_item_ids(), _create_new_scenario(), _definition_map(), _definition_name(), _definition_options() (+31 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (4): _extract_social_target(), Orchestrator - The Temporal Controller of Silicon Frontier  Manages the simulati, SocialMatrix - The Relational Database of Silicon Frontier  Tracks interpersonal, WorldState - The Physics Engine of Silicon Frontier  Provides the "Ground Truth"

### Community 8 - "Community 8"
Cohesion: 0.24
Nodes (13): bundle_root(), ensure_runtime_dirs(), is_frozen(), Helpers for locating bundled resources and writable runtime directories., Directory containing packaged resources., Directory the user interacts with at runtime., resource_path(), runtime_root() (+5 more)

### Community 10 - "Community 10"
Cohesion: 1.0
Nodes (1): Return the name of the closest relationship preset for these values.

### Community 11 - "Community 11"
Cohesion: 1.0
Nodes (1): Split a whisper target into message and recipient when present.

### Community 12 - "Community 12"
Cohesion: 1.0
Nodes (1): Return normalized names that may be used to refer to a system.

### Community 13 - "Community 13"
Cohesion: 1.0
Nodes (1): Return the required tool for a system action, if configured.

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): Return visible in-hand items from the snapshot inventory.

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): Heuristic for servers that reject structured-output fields.

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): Best-effort extraction of text content from OpenAI-compatible responses.

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): Return an emotional tag to append to a witness memory, based on relationship sta

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): Parse an action target into (item_or_message, target_agent_id).

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): Load relationships from JSON string.

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): Load world state from a JSON file.

## Knowledge Gaps
- **138 isolated node(s):** `Return selectable tool/item IDs for system requirements.`, `Return a friendly label for a tool dropdown option.`, `Render the common agent fields and return a dict of current widget values.`, `Render consumable effect sub-fields; return the current dict of values.`, `Windows launcher used for packaged builds.` (+133 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 10`** (1 nodes): `Return the name of the closest relationship preset for these values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 11`** (1 nodes): `Split a whisper target into message and recipient when present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (1 nodes): `Return normalized names that may be used to refer to a system.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 13`** (1 nodes): `Return the required tool for a system action, if configured.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (1 nodes): `Return visible in-hand items from the snapshot inventory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `Heuristic for servers that reject structured-output fields.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `Best-effort extraction of text content from OpenAI-compatible responses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `Return an emotional tag to append to a witness memory, based on relationship sta`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `Parse an action target into (item_or_message, target_agent_id).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Load relationships from JSON string.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `Load world state from a JSON file.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `WorldState` connect `Community 0` to `Community 1`, `Community 2`, `Community 5`, `Community 7`?**
  _High betweenness centrality (0.224) - this node is a cross-community bridge._
- **Why does `FrontierAgent` connect `Community 4` to `Community 0`, `Community 1`, `Community 2`, `Community 5`?**
  _High betweenness centrality (0.116) - this node is a cross-community bridge._
- **Why does `items()` connect `Community 6` to `Community 0`, `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 7`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Are the 69 inferred relationships involving `WorldState` (e.g. with `_Tee` and `SimulationState`) actually correct?**
  _`WorldState` has 69 INFERRED edges - model-reasoned connections that need verification._
- **Are the 42 inferred relationships involving `ActionParser` (e.g. with `_Tee` and `SimulationState`) actually correct?**
  _`ActionParser` has 42 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `Orchestrator` (e.g. with `_Tee` and `SimulationState`) actually correct?**
  _`Orchestrator` has 39 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `FrontierAgent` (e.g. with `_Tee` and `SimulationState`) actually correct?**
  _`FrontierAgent` has 37 INFERRED edges - model-reasoned connections that need verification._