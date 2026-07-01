#!/usr/bin/env python3
"""
Silicon Frontier - Main Simulation Entry Point

Run a complete simulation with the configured agents and world state.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class _Tee:
    """Mirror all writes to both the original stream and a log file."""

    def __init__(self, stream, log_path: Path):
        self._stream = stream
        self._file = open(log_path, "w", encoding="utf-8")

    def write(self, data):
        self._stream.write(data)
        self._file.write(data)

    def flush(self):
        self._stream.flush()
        self._file.flush()

    def close(self):
        self._file.close()

    # Proxy any other attribute access to the underlying stream
    def __getattr__(self, name):
        return getattr(self._stream, name)


def _start_logging(scenario: str) -> _Tee | None:
    """Redirect stdout to both terminal and a timestamped log file."""
    log_dir = data_path("logs")
    log_dir.mkdir(exist_ok=True)
    slug = Path(scenario).name.replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{timestamp}_{slug}.log"
    tee = _Tee(sys.stdout, log_path)
    sys.stdout = tee
    print(f"Logging to: {log_path}")
    return tee


def _stop_logging(tee: _Tee | None) -> None:
    if tee is not None:
        sys.stdout = tee._stream
        tee.close()

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))
from app_paths import bootstrap_runtime, data_path

bootstrap_runtime()

from worldstate import WorldState
from agent import FrontierAgent
from actionparser import ActionParser
from socialmatrix import SocialMatrix
from orchestrator import Orchestrator
from settings import get_llm_base_url, get_llm_model, get_config_dir, get_rounds, get_delay_seconds, get_log_file, get_random_seed
from configloader import (
    load_agent_configuration,
    build_agent_instances,
    load_item_library,
    load_scenario_manifest,
    load_relationship_presets,
    resolve_item_placements,
    resolve_relationship_presets,
)


def load_config(
    config_dir: str | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None
) -> tuple[WorldState, list[FrontierAgent]]:
    """Load world state and agent configurations from JSON files."""
    resolved_config_dir = config_dir if config_dir is not None else get_config_dir()
    config_path = Path(resolved_config_dir)

    # Load and resolve world state
    import json as _json
    try:
        with open(config_path / "world_state.json", "r") as f:
            world_data = _json.load(f)
    except (OSError, _json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to load world_state.json from '{config_path}': {exc}") from exc
    item_library = load_item_library()
    resolve_item_placements(world_data, item_library)

    agent_definitions, simulation_slots = load_agent_configuration(config_path)

    presets = load_relationship_presets()
    resolve_relationship_presets(simulation_slots, world_data, presets)

    world_state = WorldState(world_data)
    agent_instances = build_agent_instances(agent_definitions, simulation_slots)

    # Initialize agents from config
    agents = []
    for agent_cfg in agent_instances:
        agent = FrontierAgent(
            agent_id=agent_cfg["agent_id"],
            name=agent_cfg["name"],
            persona=agent_cfg["persona"],
            secret_goal=agent_cfg["secret_goal"],
            role=agent_cfg.get("role"),
            perception=agent_cfg.get("perception", 50),
            condition=agent_cfg.get("condition"),
            llm_base_url=llm_base_url,
            llm_model=llm_model
        )

        # Set starting location and inventory
        world_state.register_agent(agent.agent_id, agent_cfg["starting_location"], name=agent_cfg.get("name"))
        for item_id in agent_cfg.get("inventory", []):
            world_state.add_item_to_agent_inventory(agent.agent_id, item_id)

        agent.definition_id = agent_cfg.get("definition_id")
        agent.slot_id = agent_cfg.get("slot_id")
        agents.append(agent)

    return world_state, agents


def run_demo_simulation(
    rounds: int | None = None,
    delay_seconds: float | None = None,
    config_dir: str | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
    random_seed: int | None = None
) -> tuple[list[list[dict]], dict]:
    """
    Run a complete demo simulation.

    Args:
        rounds: Number of cycles to run
        delay_seconds: Sleep between cycles (set to 0 for fast execution)
        llm_base_url: URL of local LLM inference engine
        llm_model: Model name to use
        random_seed: Optional seed for reproducible turn order

    Returns:
        Tuple of (all_cycle_results, final_relationships)
    """
    print("\n" + "="*60)
    print("🚀 SILICON FRONTIER - DEMO SIMULATION")
    print("="*60)

    # Load configuration
    world_state, agents = load_config(config_dir=config_dir, llm_base_url=llm_base_url, llm_model=llm_model)
    scenario_manifest = load_scenario_manifest(config_dir)

    print(f"\n📍 World loaded: {len(world_state.locations)} locations, "
          f"{len(world_state.items)} items")
    print(f"👥 Agents initialized: {[a.name for a in agents]}")

    # Initialize components
    action_parser = ActionParser(world_state)
    social_matrix = SocialMatrix()
    orchestrator = Orchestrator(
        agents=agents,
        world_state=world_state,
        action_parser=action_parser,
        social_matrix=social_matrix,
        reflection_interval=5,  # Reflect every 5 cycles
        progression_config=scenario_manifest.get("progression"),
        resolution_config=scenario_manifest.get("resolution_rules"),
        random_seed=random_seed
    )

    # Run simulation
    all_results = orchestrator.run_simulation(rounds=rounds, delay_seconds=delay_seconds)

    # Print final state summary
    print("\n" + "="*60)
    print("📊 FINAL STATE SUMMARY")
    print("="*60)

    for agent in agents:
        loc = world_state.get_agent_location(agent.agent_id)
        inventory = [item["name"] for item in world_state.find_items_by_owner(agent.agent_id)]
        print(f"\n{agent.name}:")
        print(f"  Location: {loc}")
        print(f"  Inventory: {', '.join(inventory) if inventory else 'empty'}")

    # Print relationships
    print("\n🤝 RELATIONSHIP MATRIX:")
    for agent in agents:
        summary = orchestrator.get_relationship_snapshot().get(agent.agent_id, {})
        print(f"\n{agent.name}'s view of others:")
        for other_id, rel_data in summary.items():
            if other_id == agent.agent_id:
                continue
            trust = rel_data["trust"]
            affinity = rel_data["affinity"]
            status = "trusted" if trust > 70 else "distrusted" if trust < 30 else "neutral"
            print(f"  {other_id}: T={trust} ({status}), A={affinity}")

    return all_results, orchestrator.get_relationship_snapshot()


def run_quick_test(
    rounds: int | None = None,
    config_dir: str | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None
) -> None:
    """Run a quick test without delays (for automated testing)."""
    run_demo_simulation(
        rounds=rounds,
        delay_seconds=0,
        config_dir=config_dir,
        llm_base_url=llm_base_url,
        llm_model=llm_model
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Silicon Frontier simulation")
    parser.add_argument(
        "--rounds", "-r",
        type=int,
        default=10,
        help="Number of simulation cycles (default: 10)"
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=0.3,
        help="Delay between cycles in seconds (default: 0.3, use 0 for fast mode)"
    )
    parser.add_argument(
        "--config-dir", "-c",
        type=str,
        default=None,
        help="Configuration directory containing world_state.json and agent config files"
    )
    parser.add_argument(
        "--url", "-u",
        type=str,
        default=None,
        help="LLM inference engine URL (overrides settings file and env var)"
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Model name to use (overrides settings file and env var)"
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Disable log file output (print to terminal only)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible turn order (default: unseeded)"
    )

    args = parser.parse_args()

    # Resolve settings with layered priority: CLI > env var > settings.json > defaults
    resolved_config_dir = get_config_dir(args.config_dir)
    resolved_llm_base_url = get_llm_base_url(args.url)
    resolved_llm_model = get_llm_model(args.model)
    resolved_rounds = get_rounds(args.rounds)
    resolved_delay = get_delay_seconds(args.delay)
    resolved_seed = get_random_seed(args.seed)

    log_file = get_log_file(None)  # CLI --log-file not yet supported; use settings/env only
    if args.no_log:
        log_file = None

    tee = None if log_file is None else _start_logging(resolved_config_dir)
    try:
        run_demo_simulation(
            rounds=resolved_rounds,
            delay_seconds=resolved_delay,
            config_dir=resolved_config_dir,
            llm_base_url=resolved_llm_base_url,
            llm_model=resolved_llm_model,
            random_seed=resolved_seed
        )
    except Exception as e:
        print(f"\n❌ Simulation error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        _stop_logging(tee)
