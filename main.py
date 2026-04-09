import signal
import threading
import http.server
import functools
import os
from iii import register_worker, InitOptions, TriggerRequest
from config import config
from functions.consolidation_pipeline import register_consolidation_pipeline_function
from functions.enrich import register_enrich_function
from logger import get_logger
from state.hybrid_search import HybridSearch
from state.kv import StateKV
from state.vector_index import VectorIndex
from triggers.api import register_api_triggers
from providers import create_fallback_provider, create_provider
from providers.embedding import create_embedding_provider

from functions.auto_forget import register_auto_forget_function
from functions.context import register_context_function
from functions.claude_bridge import register_claude_bridge_function
from functions.compress import register_compress_function
from functions.dedup import DedupMap
from functions.file_context import register_file_context_function
from functions.observe import register_observe_function
from functions.privacy import register_privacy_function
from functions.remember import register_remember_function
from functions.search import get_search_index, register_search_function
from functions.smart_search import register_smart_search_fn
from functions.summarize import register_summarize_function
from functions.timeline import register_timeline_function

logger = get_logger("main")


def main():
    provider = (
        create_fallback_provider(
            config.provider_config, config.fallback_config)
        if config.fallback_providers
        else create_provider(config.provider_config)
    )

    embedding_provider = create_embedding_provider()

    logger.info("starting worker ...")
    logger.info("engine:   %s", config.engine_url)
    logger.info("provider: %s (%s)", config.provider, config.model)
    logger.info("REST API: http://localhost:%s/graphmind/*", config.rest_port)
    logger.info("streams:  ws://localhost:%s", config.streams_port)

    viewer_port = config.rest_port - 1
    viewer_dir = os.path.join(os.path.dirname(__file__), "viewer")
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=viewer_dir,
    )
    viewer_server = http.server.HTTPServer(("", viewer_port), handler)
    viewer_thread = threading.Thread(
        target=viewer_server.serve_forever, daemon=True)
    viewer_thread.start()
    logger.info("viewer:   http://localhost:%s/?restPort=%s",
                viewer_port, config.rest_port)

    if embedding_provider:
        logger.info("embedding: %s (%s dims)",
                    embedding_provider.name, embedding_provider.dimensions)
    else:
        logger.info("embedding: none (BM25-only mode)")

    sdk = register_worker(
        config.engine_url, InitOptions(worker_name="graphmind"))
    kv = StateKV(sdk=sdk)

    dedup_map = DedupMap()

    register_observe_function(
        sdk, kv, dedup_map, config.max_observations_per_session)
    register_compress_function(sdk, kv, provider)
    register_context_function(sdk, kv, config.token_budget)
    register_summarize_function(sdk, kv, provider)
    register_privacy_function(sdk)
    register_remember_function(sdk, kv)
    register_file_context_function(sdk, kv)
    register_search_function(sdk, kv)
    register_timeline_function(sdk, kv)
    register_auto_forget_function(sdk, kv)
    register_enrich_function(sdk, kv)

    # Search functionality
    bm25_index = get_search_index()
    vector_index = VectorIndex() if embedding_provider != None else None
    hybrid_search = HybridSearch(
        kv,
        bm25_index,
        vector_index,
        embedding_provider,
        config.bm25_weight,
        config.vector_weight
    )
    register_smart_search_fn(sdk, kv, hybrid_search.search)
    if config.bridge_config.enabled:
        register_claude_bridge_function(sdk, kv, config.bridge_config)
        logger.info("claude bridge → %s",
                    config.bridge_config.memory_file_path)

    register_consolidation_pipeline_function(
        sdk, kv, provider, config.consolidate_pipeline_config)
    logger.info(
        f"[graphmind] Consolidation pipeline: registered(CONSOLIDATION_ENABLED={"true" if config.consolidate_pipeline_config.enabled else "false"}")

    register_api_triggers(sdk, kv)

    stop_event = threading.Event()

    if config.consolidate_pipeline_config.enabled:
        consolidation_interval_s = config.consolidate_pipeline_config.interval

        def _auto_consolidate():
            while not stop_event.wait(timeout=consolidation_interval_s):
                logger.info("auto-consolidation: triggering pipeline")
                try:
                    result = sdk.trigger(TriggerRequest(
                        function_id="mem::consolidate-pipeline",
                        payload={},
                    ))
                    logger.info("auto-consolidation: completed result=%s", result)
                except Exception as err:
                    logger.warning("auto-consolidation: trigger failed error=%s", err)

        threading.Thread(target=_auto_consolidate, daemon=True,
                         name="auto-consolidation").start()
        logger.info("auto-consolidation: enabled (every %dm)", consolidation_interval_s // 60)

    def shutdown(*_):
        # Reset to default immediately so a second Ctrl+C force-kills
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    stop_event.wait()

    # Cleanup runs on main thread after unblocking — never inside the signal handler
    logger.info("shutting down")
    dedup_map.stop()
    sdk.shutdown()


if __name__ == "__main__":
    main()
