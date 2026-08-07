# Graph Report - .  (2026-08-07)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 867 nodes · 1623 edges · 83 communities (72 shown, 11 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 102 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0ed63efe`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- settings.py
- configloader.py
- scenario_editor.py
- WorldState
- actionparser.py
- ._validate_decision_against_telemetry
- .items
- app_paths.py
- SocialMatrix
- agent.py
- Any
- FrontierAgent
- Any
- dashboard.py
- ._hand_items
- Orchestrator
- .run_cycle
- .load
- ActionParser
- .get_snapshot_for_agent
- SimulationState
- .think_and_act
- ._matches_entity
- Silicon Frontier User Manual
- test_parallel_social_critic.py
- ._required_tool_for_action
- Any
- How the Simulation Works
- render_agent_library_controls
- ._handle_demand
- ._normalize_condition
- ._apply_item_effect
- ._apply_social_critic_update
- tool_registry.py
- test_system_status.py
- Editing Configuration
- scenario_resolution.py
- test_prisoners_dilemma.py
- _Agent
- render_model_role_selector
- .assess_message_against_telemetry
- .get_relationship_summary
- ._sync_relationships
- .get_or_create_relationship
- .get_location_systems
- Scenario Editor
- Run the dashboard
- _Tee
- ._effect_state
- ._update_progression_pressure
- test_fabrication.py
- orchestrator.md
- process_queued_cycles
- ._evaluate_social_impact
- .transfer_item_between_agents
- Quick Start
- Q: Why does WorldState connect so many otherwise separate subsystems?
- .from_json
- Troubleshooting
- render_agent_card
- ._apply_read_side_effects
- Fabrication
- Shared Library System
- Sabotage-Driven Scenarios
- Operational Notes
- .to_json
- .add_item
- Technical Specifications Document
- Streamlit dashboard UI
- The Orchestrator Script
- The Reflection System
- The Relationship Matrix
- Prisoner's Dilemma Scenario
- Handling Social Presence
- JSON World State

## God Nodes (most connected - your core abstractions)
1. `WorldState` - 76 edges
2. `FrontierAgent` - 72 edges
3. `Orchestrator` - 64 edges
4. `ActionParser` - 59 edges
5. `SocialMatrix` - 30 edges
6. `SimulationState` - 28 edges
7. `main()` - 25 edges
8. `Silicon Frontier User Manual` - 22 edges
9. `_Tee` - 14 edges
10. `_resolve_str()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `_Tee` --uses--> `ActionParser`  [INFERRED]
  run_simulation.py → src/actionparser.py
- `_Tee` --uses--> `FrontierAgent`  [INFERRED]
  run_simulation.py → src/agent.py
- `_Tee` --uses--> `Orchestrator`  [INFERRED]
  run_simulation.py → src/orchestrator.py
- `_Tee` --uses--> `SocialMatrix`  [INFERRED]
  run_simulation.py → src/socialmatrix.py
- `_Tee` --uses--> `WorldState`  [INFERRED]
  run_simulation.py → src/worldstate.py

## Import Cycles
- None detected.

## Communities (83 total, 11 thin omitted)

### Community 0 - "settings.py"
Cohesion: 0.06
Nodes (57): _find_legacy_settings_file(), _find_settings_file(), get_all_settings(), get_api_key(), get_config_dir(), get_dashboard_host(), get_dashboard_port(), get_delay_seconds() (+49 more)

### Community 1 - "configloader.py"
Cohesion: 0.08
Nodes (43): load_config(), Path, Run a complete demo simulation. Args: rounds: Number of cycles to run…, Mirror all writes to both the original stream and a log file., Run a quick test without delays (for automated testing)., Redirect stdout to both terminal and a timestamped log file., Load world state and agent configurations from JSON files., run_demo_simulation() (+35 more)

### Community 2 - "scenario_editor.py"
Cohesion: 0.13
Nodes (43): _active_slot_def_ids(), _agent_condition(), _agent_fields(), _agent_library(), _all_item_ids(), _crafting_catalog(), _crafting_validation_issues(), _create_new_scenario() (+35 more)

### Community 3 - "WorldState"
Cohesion: 0.09
Nodes (13): Any, Return facts known by one agent., Return one agent's current relationship view of another., Add a new location to the world., The central truth table for the simulation environment. This class enforces…, Find a route through exits the agent has already discovered., Initialize world state from dict or empty., Check if two locations are connected. (+5 more)

### Community 4 - "actionparser.py"
Cohesion: 0.10
Nodes (13): ActionParser - The System Arbiter of Silicon Frontier Validates and executes…, SocialMatrix - The Relational Database of Silicon Frontier Tracks interpersonal…, WorldState - The Physics Engine of Silicon Frontier Provides the "Ground Truth"…, main(), Verify unresolved critical systems keep applying simulation pressure., StubAgent, Agent, main() (+5 more)

### Community 5 - "._validate_decision_against_telemetry"
Cohesion: 0.11
Nodes (13): Choose one concrete next step toward stabilizing a known system fault., Choose a covert preparation step instead of wasting a witnessed sabotage turn., Choose a productive next step without using movement as filler., Produce a compact menu of deterministic, legal next actions., Correct system actions that contradict live telemetry., Return the agent's explicit or legacy-inferred secret assignment., Normalize item/system labels so ids and display names compare predictably., Parse transfer-style targets into (item, agent_id). (+5 more)

### Community 6 - ".items"
Cohesion: 0.12
Nodes (11): Return a defensive copy of the agent's discovered map., Return recipes that can be assembled at one of this location's facilities., Find visible or carried stacks of a named fabrication material., Validate the deterministic preconditions for a fabrication attempt., Consume recipe materials and create one declarative in-world tool., Find all items at a specific location., Find all items owned by an agent., Get an agent's current location. (+3 more)

### Community 7 - "app_paths.py"
Cohesion: 0.19
Nodes (20): _find_available_port(), _launch_cli(), _launch_streamlit(), main(), Windows launcher used for packaged builds., atomic_write_json(), bootstrap_runtime(), bundle_root() (+12 more)

### Community 8 - "SocialMatrix"
Cohesion: 0.12
Nodes (10): Manages relationship scores between all agents in the simulation. Each agent…, Get a network view of trust relationships. Returns: Dict mapping agent_id to…, Load relationships from JSON string., Initialize the social matrix., Populate relationships from world state data., Mirror the active relationship matrix back into the world state., Ensure a hidden suspicion entry exists for the observer-target pair., Get suspicion from one agent's perspective toward another. (+2 more)

### Community 9 - "agent.py"
Cohesion: 0.13
Nodes (12): Return whether an unmet environmental condition merits one new choice. These…, FrontierAgent - The Cognitive Unit of Silicon Frontier Represents an autonomous…, main(), Focused checks for goal-alignment and inventory preflight corrections., validate(), _agent(), _FailingClient, _FailingCompletions (+4 more)

### Community 10 - "Any"
Cohesion: 0.15
Nodes (9): Any, Handle SAY action - returns success but actual broadcasting is done by…, Return the configured required tool, or None when the action only needs an…, Normalize optional tool fields; None/empty/'none'/'null' means no tool required., Check whether the agent is visibly holding the required tool., Validate and execute an agent's action. Args: agent: FrontierAgent instance…, Handle LIE action as a flagged speech act., Handle SABOTAGE action on a local system. (+1 more)

### Community 11 - "FrontierAgent"
Cohesion: 0.10
Nodes (12): FrontierAgent, Build an experiential memory string from an action outcome. Richer than a bare…, Return a compact private-plan summary for the fast action model., Return condition as compact prompt text., Return behavioral nudges for extreme condition values., Apply a validated planner result after the orchestrator orders reviews., Add an event to the short-term memory buffer (max 10 events)., Update the agent's current emotional state. (+4 more)

### Community 12 - "Any"
Cohesion: 0.19
Nodes (8): Any, Record a concise, actionable LLM failure without exposing a traceback to…, Best-effort extraction of text content from OpenAI-compatible responses., Parse a decision object from a model response., Condense short-term memory into long-term memory. Called periodically (e.g.,…, Ask the strategic model for intent only; it cannot execute an action., Generate a subjective view of the world for the agent. This filters the…, Use the local model as a hidden critic for relationship updates.

### Community 13 - "dashboard.py"
Cohesion: 0.18
Nodes (15): main(), Render recent hidden-critic work so model usage is auditable., Render periodic strategic-planning work separately from social critics., Render researcher-focused audit tools for deception and sabotage., Render the God Console for experimental intervention., Render the relationship matrix visualization., Render the event log., Render a filtered log of all inter-agent communications. (+7 more)

### Community 14 - "._hand_items"
Cohesion: 0.17
Nodes (7): Return the agent's in-hand inventory item., Handle PICKUP action., Assemble one scenario-authored tool from local/carried materials., Handle CONCEAL action — move an item from hand to the concealed person slot., Handle PRODUCE action — move a concealed item from person slot to hand., Move an in-hand item to the visible carried slot., Move a visible carried item into the hand slot.

### Community 15 - "Orchestrator"
Cohesion: 0.15
Nodes (8): Orchestrator, Orchestrator - The Temporal Controller of Silicon Frontier Manages the…, Inject a global event (God Console functionality). This allows external…, Manually set an agent's location (God Console)., Finalize an opt-in scenario once all required agents have scorable decisions., Central controller for the simulation loop. Manages: - Turn ordering and…, Return an emotional tag to append to a witness memory, based on relationship…, Broadcast an action to all witnesses in a location, appending an emotionally-…

### Community 16 - ".run_cycle"
Cohesion: 0.13
Nodes (8): Keep the first trigger for an agent until the review phase., Run independent planner calls concurrently and apply them deterministically., Record who was where at the start of a cycle for later audits., Escalate unresolved OFFLINE/BROKEN systems once per cycle., Print the current status of every system in the station., Resolve an action target to a local system id when possible., Parse an action target into (item_or_message, target_agent_id)., Execute a single simulation cycle (all agents take one turn). Returns: List of…

### Community 17 - ".load"
Cohesion: 0.16
Nodes (8): Path, Rebuild world-facing agent objects from current definitions and slots., Initialize the simulation from JSON configs., Write scenario asset files from the current session or a selected save file., Serialize full simulation state to a JSON file., Restore simulation state from a saved JSON file., Return sorted list of save files, newest first., _start_logging()

### Community 18 - "ActionParser"
Cohesion: 0.18
Nodes (7): ActionParser, Check optional item-gated access requirements for a destination., Validates agent actions against world physics and updates state accordingly.…, Initialize the action parser with a reference to the world state. Args:…, Find an item the agent is carrying or can see in their current room., Handle READ action - learn knowledge from an accessible item., Handle SHOW action: SHOW item -> agent_id.

### Community 19 - ".get_snapshot_for_agent"
Cohesion: 0.18
Nodes (7): Return one agent's hidden suspicion score toward another., Get location details by ID., Return normalized fabrication facilities available at a location., Record a room's local details and reveal its direct exits to an agent., Update an agent's current location., Register a new agent in the world state., Get a filtered view of the world suitable for an agent's Sense phase. This is…

### Community 20 - "SimulationState"
Cohesion: 0.15
Nodes (7): Manages simulation state across Streamlit sessions., Persist the definition selected for an active simulation slot., Schedule one or more cycles to run across Streamlit reruns., Restore locations to baseline from original world_state.json., Restore items to baseline (original locations/owners, no agent inventory)., Restore agents to baseline positions, inventory, and memory., SimulationState

### Community 21 - ".think_and_act"
Cohesion: 0.17
Nodes (7): Exception, Return the ideal structured-output schema for an agent turn., Heuristic for servers that reject structured-output fields., Create a chat completion, optionally requesting structured output., Execute the Think/Act phase by calling the LLM. Args: observation: The…, Give an agent one informed replacement choice after a preempted action. This is…, Return a safe decision payload that conforms to the expected schema.

### Community 22 - "._matches_entity"
Cohesion: 0.15
Nodes (6): Normalize model-facing labels and stable ids into a comparable form., Match ids and display names while tolerating spaces, underscores, and case., Handle USE action — trigger a held item's configured effect., Split `USE tool -> system` without changing existing `USE tool` syntax., Pre-validate a MOVE action without executing., Pre-validate a PICKUP action without executing.

### Community 23 - "Silicon Frontier User Manual"
Cohesion: 0.15
Nodes (12): CONCEAL and PRODUCE Actions, Item Placements (Library Reference Pattern), Known Caveats, Overview, Project Layout, Recommended Workflow, Relationship Presets in `simulation_agents.json`, Requirements (+4 more)

### Community 24 - "test_parallel_social_critic.py"
Cohesion: 0.25
Nodes (6): Lock, check(), FakeAgent, FakeWorld, main(), Verify social-witness critics run concurrently but mutate state…

### Community 25 - "._required_tool_for_action"
Cohesion: 0.18
Nodes (5): Release only a disposable item when it unlocks a strictly better pickup., Return the required tool for a system action; None means no tool required., Normalize optional tool fields; None/empty/'none'/'null' means no tool required., Format system tool requirements for prompt text., Rank carried items conservatively for deterministic capacity decisions.

### Community 26 - "Any"
Cohesion: 0.18
Nodes (6): Any, Run the full simulation for a specified number of rounds. Args: rounds: Number…, Get the complete event log for analysis., Get current relationship scores., Initialize the orchestrator. Args: agents: List of FrontierAgent instances…, Record speech heard by a listener as durable knowledge.

### Community 27 - "How the Simulation Works"
Cohesion: 0.18
Nodes (11): Agent actions, Audience awareness, Emotional state, How the Simulation Works, Inventory, Memory and reflection, Parallel social critics, Social scores (+3 more)

### Community 28 - "render_agent_library_controls"
Cohesion: 0.20
Nodes (6): Render reusable agent definition and active slot selection controls., Persist the full editable state of an active simulation slot., Add a new active simulation slot and persist it., Remove an active simulation slot and persist the updated set., Add a new reusable agent definition and persist it., render_agent_library_controls()

### Community 29 - "._handle_demand"
Cohesion: 0.24
Nodes (5): Parse an action target into (item, agent_id)., Resolve a target agent only if they are currently visible., Handle GIVE action: GIVE item -> agent_id., Handle DEMAND action: DEMAND item -> agent_id., Handle WHISPER action: WHISPER message -> agent_id.

### Community 30 - "._normalize_condition"
Cohesion: 0.22
Nodes (5): Infer the legacy assignment from old scenario goals or role labels., Clamp a numeric value to the valid 0-100 range used by condition/perception…, Return a complete, clamped condition block for an agent., Apply clamped condition deltas and return changed fields., Initialize an agent with its cognitive profile. Args: agent_id: Unique…

### Community 31 - "._apply_item_effect"
Cohesion: 0.29
Nodes (5): Apply configured effects when scenario pressure crosses a threshold., Send an event to all agents in a specific room. Args: message: The event…, Apply configured consequences for a system status change., Apply configured perception, mood, and condition effects to an agent., Apply an item's effect fields to the picking agent, then delete it if…

### Community 32 - "._apply_social_critic_update"
Cohesion: 0.20
Nodes (5): Fallback heuristic if the social critic is unavailable., Fallback heuristic for hidden suspicion changes., Get an observer-specific relationship update without mutating state., Apply one already-evaluated critic result on the orchestrator thread., Synchronously evaluate and apply one critic update (test/helper path).

### Community 33 - "tool_registry.py"
Cohesion: 0.27
Nodes (8): _matches(), _normalize(), Any, Deterministic registry for target-aware fabricated-tool capabilities., Validate a fabricated tool's declared capability and optional target.…, validate_tool_use(), main(), Regression checks for durable, target-aware default-scenario tool use.

### Community 34 - "test_system_status.py"
Cohesion: 0.20
Nodes (3): PromptProbeAgent, Test: agent SABOTAGE and REPAIR actions for system status changes. Test 1 — no…, StubAgent

### Community 35 - "Editing Configuration"
Cohesion: 0.20
Nodes (10): Active simulation slots, Add or change items, Add or change locations, Agent definitions, Contested items, Editing Configuration, Example: Prisoner's Dilemma, Hidden items (+2 more)

### Community 36 - "scenario_resolution.py"
Cohesion: 0.42
Nodes (8): classify_prisoners_dilemma_action(), _contains_any(), evaluate_prisoners_dilemma(), _merge_rules(), Any, Scenario-specific resolution helpers., Evaluate the final prisoner choices and sentence payoffs from an event log., Classify one event-log entry as silent/cooperate, or None if not decisive.

### Community 37 - "test_prisoners_dilemma.py"
Cohesion: 0.31
Nodes (4): check(), event(), main(), PressureAgent

### Community 38 - "_Agent"
Cohesion: 0.28
Nodes (4): _Agent, main(), Focused checks for the optional strategic-reasoning review phase., _World

### Community 39 - "render_model_role_selector"
Cohesion: 0.25
Nodes (5): Render one consistent endpoint + fetched-model control for an LLM role., Fetch model IDs from an OpenAI-compatible /models endpoint., Return the model IDs most recently fetched for one endpoint., Return the latest fetch error for one endpoint, if any., render_model_role_selector()

### Community 40 - ".assess_message_against_telemetry"
Cohesion: 0.25
Nodes (4): Return a concise note when a heard claim contradicts telemetry., Return normalized names that may be used to refer to a system., Detect claims in text that contradict the current telemetry., Build a flat list of systems and statuses available to the agent this turn.

### Community 41 - ".get_relationship_summary"
Cohesion: 0.33
Nodes (3): Any, Get a summary of all relationships for an agent., Get all relationships in the matrix.

### Community 42 - "._sync_relationships"
Cohesion: 0.25
Nodes (4): Keep world-state relationship data aligned with the social matrix., Store a sabotage incident with recent room occupancy context., High-perception witnesses can receive covert suspicion memories., Let a listener compare a spoken system claim against known telemetry.

### Community 43 - ".get_or_create_relationship"
Cohesion: 0.20
Nodes (5): Get trust and affinity scores from agent_a's perspective of agent_b. Args:…, Update relationship scores with deltas. Args: agent_a: The observer (who is…, Directly set relationship scores (bypassing deltas)., Ensure every agent has a neutral relationship entry for every other agent., Ensure a relationship entry exists for both agents. Returns: Tuple of…

### Community 45 - ".get_location_systems"
Cohesion: 0.25
Nodes (4): Get the system map for a location., Update a named system in a location., Return the configured consequence block for a system status., Apply world-state side effects configured for a system status. Consequences can…

### Community 46 - "Scenario Editor"
Cohesion: 0.25
Nodes (8): Agent Definitions tab, Items tab, Locations tab, Relationships tab, Scenario Editor, Scenario tab, Sidebar, Simulation Slots tab

### Community 47 - "Run the dashboard"
Cohesion: 0.25
Nodes (8): Agent panel, God Console, Main controls, Map knowledge, Relationship Matrix, Run the dashboard, Save and load, World State editor

### Community 48 - "_Tee"
Cohesion: 0.33
Nodes (3): Mirror all writes to both the original stream and a log file., _stop_logging(), _Tee

### Community 49 - "._effect_state"
Cohesion: 0.33
Nodes (3): Return a stable key for an action whose result can become stale., Describe the relevant observed state, allowing repeats after a change., Keep compact, factual progress state after an executed action.

### Community 50 - "._update_progression_pressure"
Cohesion: 0.33
Nodes (3): Return whether scenario pressure progression is active., Return whether an action target matches configured progression phrases., Update scenario pressure after an action and fire newly crossed thresholds.

### Community 51 - "test_fabrication.py"
Cohesion: 0.43
Nodes (5): build_world(), check(), main(), Validate deterministic in-world fabrication and agent-facing affordances., StubAgent

### Community 52 - "orchestrator.md"
Cohesion: 0.33
Nodes (5): ActionParser, Query: Why does WorldState connect so many otherwise separate subsystems?, --- INITIAL WORLD STATE ---, --- INITIALIZE AGENTS ---, --- THE MAIN SIMULATION LOOP ---

### Community 53 - "process_queued_cycles"
Cohesion: 0.40
Nodes (4): process_queued_cycles(), Stop any queued simulation run., Execute a single cycle and record the results., Run at most one queued cycle per rerun so Stop can interrupt cleanly.

### Community 54 - "._evaluate_social_impact"
Cohesion: 0.33
Nodes (3): Evaluate relationship impact for observed social actions. Uses the observer-…, Inject a false memory into an agent's long-term storage. Args: agent_id: Target…, Find an agent by their ID.

### Community 55 - ".transfer_item_between_agents"
Cohesion: 0.33
Nodes (3): Add an item to an agent's inventory., Remove an item from an agent's inventory., Move an item directly from one agent's inventory to another's.

### Community 56 - "Quick Start"
Cohesion: 0.33
Nodes (6): Build the Windows executable, Logging, Quick Start, Run in the terminal, Run the packaged executable, Run the scenario editor

### Community 57 - "Q: Why does WorldState connect so many otherwise separate subsystems?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Why does WorldState connect so many otherwise separate subsystems?, Source Nodes

### Community 58 - ".from_json"
Cohesion: 0.40
Nodes (3): Path, Load world state from a JSON file., Save current state to a JSON file.

### Community 59 - "Troubleshooting"
Cohesion: 0.40
Nodes (5): Agents are stuck dropping an item every turn, Agents keep failing actions, Save files do not appear, The simulation cannot reach the model, Troubleshooting

### Community 60 - "render_agent_card"
Cohesion: 0.50
Nodes (3): Persist selected definition fields back to the reusable agent catalog., Render a clickable agent card that opens an editor when expanded., render_agent_card()

### Community 62 - "Fabrication"
Cohesion: 0.50
Nodes (4): ASSEMBLE action, Configure facilities, materials, and recipes, Default scenario resource economy, Fabrication

### Community 63 - "Shared Library System"
Cohesion: 0.50
Nodes (4): `library/agents.json`, `library/items.json`, `library/relationship_presets.json`, Shared Library System

### Community 64 - "Sabotage-Driven Scenarios"
Cohesion: 0.67
Nodes (3): Example: Four-Agent Cooperative Scenario, Example: Four-Agent Rogue Scenario, Sabotage-Driven Scenarios

### Community 65 - "Operational Notes"
Cohesion: 0.67
Nodes (3): LLM integration, Operational Notes, Terminal output

## Knowledge Gaps
- **78 isolated node(s):** `Overview`, `Project Layout`, `Requirements`, `Run in the terminal`, `Logging` (+73 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `FrontierAgent` connect `FrontierAgent` to `configloader.py`, `test_system_status.py`, `actionparser.py`, `._validate_decision_against_telemetry`, `.assess_message_against_telemetry`, `agent.py`, `Any`, `_Tee`, `.load`, `._effect_state`, `SimulationState`, `.think_and_act`, `._required_tool_for_action`, `._normalize_condition`?**
  _High betweenness centrality (0.222) - this node is a cross-community bridge._
- **Why does `WorldState` connect `WorldState` to `configloader.py`, `tool_registry.py`, `.add_item`, `actionparser.py`, `test_prisoners_dilemma.py`, `.items`, `test_system_status.py`, `.get_location_systems`, `_Tee`, `.load`, `ActionParser`, `.get_snapshot_for_agent`, `SimulationState`, `test_fabrication.py`, `._matches_entity`, `.transfer_item_between_agents`, `.from_json`?**
  _High betweenness centrality (0.212) - this node is a cross-community bridge._
- **Why does `Orchestrator` connect `Orchestrator` to `._apply_social_critic_update`, `configloader.py`, `test_system_status.py`, `actionparser.py`, `test_prisoners_dilemma.py`, `_Agent`, `._sync_relationships`, `_Tee`, `.load`, `.run_cycle`, `._update_progression_pressure`, `SimulationState`, `._evaluate_social_impact`, `test_parallel_social_critic.py`, `Any`, `._apply_read_side_effects`, `._apply_item_effect`?**
  _High betweenness centrality (0.191) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `WorldState` (e.g. with `SimulationState` and `.initialize()`) actually correct?**
  _`WorldState` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `FrontierAgent` (e.g. with `SimulationState` and `._build_runtime_from_loaded_config()`) actually correct?**
  _`FrontierAgent` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Orchestrator` (e.g. with `SimulationState` and `._build_runtime_from_loaded_config()`) actually correct?**
  _`Orchestrator` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `ActionParser` (e.g. with `SimulationState` and `._build_runtime_from_loaded_config()`) actually correct?**
  _`ActionParser` has 18 INFERRED edges - model-reasoned connections that need verification._