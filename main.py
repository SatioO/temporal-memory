import signal
import threading
from iii import register_worker, InitOptions

from config import config
from functions.claude_bridge import register_claude_bridge_function
from functions.context import register_context_function
from functions.dedup import DedupMap
from functions.observe import register_observe_function
from functions.summarize import register_summarize_function
from functions.team import register_team_function
from providers.embedding import create_embedding_provider
from providers import create_fallback_provider, create_provider
from state.kv import StateKV
from triggers.api import register_api_triggers


def main():
    provider = (
        create_fallback_provider(config.provider_config, config.fallback_config)
        if config.fallback_providers
        else create_provider(config.provider_config)
    )

    embedding_provider = create_embedding_provider()

    print(f"[graphmind] starting worker ...")
    print(f"[graphmind] engine:   {config.engine_url}")
    print(f"[graphmind] provider: {config.provider} ({config.model})")
    print(f"[graphmind] REST API: http://localhost:{config.rest_port}/graphmind/*")
    print(f"[graphmind] streams:  ws://localhost:{config.streams_port}")

    if embedding_provider:
        print(f"[graphmind] embedding: {embedding_provider.name} ({embedding_provider.dimensions} dims)")
    else:
        print(f"[graphmind] embedding: none (BM25-only mode)")

    sdk = register_worker(config.engine_url, InitOptions(worker_name="graphmind"))
    kv  = StateKV(sdk=sdk)

    dedup_map = DedupMap()

    register_observe_function(sdk, kv, dedup_map, config.max_observations_per_session)
    register_context_function(sdk, kv, config.token_budget)
    register_summarize_function(sdk, kv, provider)

    if config.team_config:
        register_team_function(sdk, kv, config.team_config)
        print(f"[graphmind] team memory: {config.team_config.team_id} ({config.team_config.mode})")

    register_api_triggers(sdk, kv)

    if config.bridge_config.enabled:
        register_claude_bridge_function(sdk, kv, config.bridge_config)
        print(f"[graphmind] claude bridge → {config.bridge_config.memory_file_path}")

    stop_event = threading.Event()

    def shutdown(*_):
        print("\n[graphmind] shutting down")
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    stop_event.wait()


if __name__ == "__main__":
    main()
