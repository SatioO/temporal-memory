import signal
import threading
from iii import OtelConfig, register_worker, InitOptions

from config import load_config, load_embedding_config, load_fallback_config, load_team_config
from functions.team import register_team_function
from model import OtelConfigSettings
from providers.embedding import create_embedding_provider
from providers import create_fallback_provider, create_provider
from state.kv import StateKV
from triggers.api import register_api_triggers


def main():
    config = load_config()
    embedding_config = load_embedding_config()
    fallback_config = load_fallback_config()

    provider = create_fallback_provider(config.provider, fallback_config)\
        if len(fallback_config.providers) > 0 \
        else create_provider(config.provider)

    embedding_provider = create_embedding_provider()

    print(f"[graphmind] starting worker ...")
    print(f"[graphmind] engine: {config.engine_url}")
    print(
        f"[graphmind] provider: {config.provider.provider} ({config.provider.model})")

    if embedding_provider:
        print(
            f"[graphmind] Embedding provider: {embedding_provider.name}({embedding_provider.dimensions} dims)",
        )
    else:
        print(f"[graphmind] Embedding provider: none (BM25-only mode)")

    print(
        f"[graphmind] REST API: http://localhost:{config.rest_port}/graphmind/*",
    )
    print(f"[graphmind] Streams: ws://localhost:{config.streams_port}")
    otel_config = OtelConfigSettings()

    sdk = register_worker(
        config.engine_url,
        InitOptions(worker_name="graphmind")
    )
    kv = StateKV(sdk=sdk)

    team_config = load_team_config()
    if team_config:
        register_team_function(sdk, kv, team_config)
        print(
            f"[graphmind] team memory: {team_config.team_id} ({team_config.mode})")

    register_api_triggers(sdk, kv)

    stop_event = threading.Event()

    def shutdown(*_):
        print("\n[graphmind] shutting down")
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    stop_event.wait()


if __name__ == "__main__":
    main()
