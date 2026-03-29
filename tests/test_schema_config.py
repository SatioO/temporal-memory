from schema.config import (
    ProviderType,
    ProviderConfig,
    AgentMemoryConfig,
    EmbeddingConfig,
    FallbackConfig,
    TeamConfig,
    CloudBridgeConfig,
    OtelConfigSettings,
)


def test_provider_config_is_dataclass():
    cfg = ProviderConfig(provider="anthropic", model="claude-3-5-sonnet-20241022", max_tokens=8096)
    assert cfg.provider == "anthropic"
    assert cfg.model == "claude-3-5-sonnet-20241022"
    assert cfg.max_tokens == 8096


def test_embedding_config_provider_is_not_quoted():
    # Bug Fix 2: Optional[str] not Optional["str"]
    cfg = EmbeddingConfig(provider=None, bm25_weight=0.5, vector_weight=0.5)
    assert cfg.provider is None
    cfg2 = EmbeddingConfig(provider="openai", bm25_weight=0.3, vector_weight=0.7)
    assert cfg2.provider == "openai"


def test_fallback_config_providers_list():
    cfg = FallbackConfig(providers=["anthropic", "openrouter"])
    assert cfg.providers == ["anthropic", "openrouter"]


def test_team_config():
    cfg = TeamConfig(team_id="t1", user_id="u1", mode="shared")
    assert cfg.mode == "shared"


def test_cloud_bridge_config():
    cfg = CloudBridgeConfig(
        enabled=True,
        project_path="/tmp/proj",
        memory_file_path="/tmp/mem.md",
        line_budget=200,
    )
    assert cfg.enabled is True


def test_otel_config_defaults():
    cfg = OtelConfigSettings()
    assert cfg.service_name == "graphmind"
    assert cfg.metrics_export_interval_ms == 30000
