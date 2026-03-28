from typing import List
from model import FallbackConfig, MemoryProvider, ProviderConfig
from providers.anthropic import AnthropicProvider
from providers.fallback_chain import FallbackChain
from providers.resilient import ResilientProvider

# TODO: add more providers


def _create_base_provider(config: ProviderConfig) -> MemoryProvider:
    provider = config.provider

    if provider == "anthropic":
        return AnthropicProvider(
            api_key="",
            model=config.model,
            max_tokens=config.max_tokens
        )

    elif provider == "gemini":
        raise NotImplementedError(f"Gemini provider is not implemented")

    elif provider == "openrouter":
        raise NotImplementedError(f"OpenRouter provider is not implemented")

    else:
        raise NotImplementedError("Agent SDK provider is not implemented")


def create_provider(config: ProviderConfig) -> ResilientProvider:
    return ResilientProvider(_create_base_provider(config))


def create_fallback_provider(config: ProviderConfig, fallback_config: FallbackConfig) -> ResilientProvider:
    if len(fallback_config.providers) == 0:
        return create_provider(config)

    providers: List[MemoryProvider] = [_create_base_provider(config)]

    for providerType in fallback_config.providers:
        if providerType == config.provider:
            continue

        try:
            fb_config = ProviderConfig(
                provider=providerType,
                max_tokens=config.max_tokens,
                model=config.model,
            )
            providers.append(_create_base_provider(fb_config))
        except:
            pass

    if len(providers) > 1:
        return ResilientProvider(FallbackChain(providers))

    return ResilientProvider(providers[0])
