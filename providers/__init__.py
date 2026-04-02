import os
from typing import List
from providers.openai import OpenAIProvider
from providers.gemini import GeminiProvider
from providers.openrouter import OpenRouterProvider
from providers.agent_sdk import AgentSDKProvider
from schema import FallbackConfig, MemoryProvider, ProviderConfig
from providers.anthropic import AnthropicProvider
from providers.fallback_chain import FallbackChain
from providers.resilient import ResilientProvider


def _create_base_provider(config: ProviderConfig) -> MemoryProvider:
    provider = config.provider

    if provider == "anthropic":
        return AnthropicProvider(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model=config.model,
            max_tokens=config.max_tokens
        )

    if provider == "openai":
        return OpenAIProvider(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=config.model,
            max_tokens=config.max_tokens
        )

    if provider == "gemini":
        return GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY"),
            model=config.model,
            max_tokens=config.max_tokens
        )

    if provider == "openrouter":
        return OpenRouterProvider(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            model=config.model,
            max_tokens=config.max_tokens
        )

    if provider == "agent-sdk":
        return AgentSDKProvider(
            model=config.model,
            max_tokens=config.max_tokens
        )

    raise ValueError(f"Unknown provider: {provider}")


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
