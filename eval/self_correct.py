from dataclasses import dataclass
from typing import Callable
from schema import MemoryProvider, Model

STRICT_PROMPT = "IMPORTANT: Your previous response was invalid. Please ensure your output strictly follows the required XML format. Every required field must be present with valid values."


@dataclass(frozen=True)
class CompressionValidationResult(Model):
    valid: bool
    errors: list[str]


@dataclass(frozen=True)
class SummarizationValidationResult(Model):
    valid: bool
    errors: list[str]


@dataclass(frozen=True)
class CompressionResult(Model):
    response: str
    retried: bool


@dataclass(frozen=True)
class SummarizationResult(Model):
    response: str
    retried: bool


async def compress_with_retry(
    provider: MemoryProvider,
    system_prompt: str,
    user_prompt: str,
    validator: Callable[[str], CompressionValidationResult],
    max_retries: int = 1
) -> CompressionResult:
    first = await provider.compress(system_prompt, user_prompt)

    result = validator(first)

    if result.valid:
        return CompressionResult(response=first, retried=False)

    for _ in range(max_retries + 1):
        retry = await provider.compress(
            system_prompt + f"\n\n {STRICT_PROMPT}", user_prompt)
        retry_result = validator(retry)
        if retry_result.valid:
            return CompressionResult(response=retry, retried=True)

    return CompressionResult(response=first, retried=True)


async def summarize_with_retry(
    provider: MemoryProvider,
    system_prompt: str,
    user_prompt: str,
    validator: Callable[[str], SummarizationValidationResult],
    max_retries: int = 1
) -> SummarizationResult:
    first = await provider.summarize(system_prompt, user_prompt)

    result = validator(first)

    if result.valid:
        return SummarizationResult(response=first, retried=False)

    for _ in range(max_retries + 1):
        retry = await provider.summarize(
            system_prompt + f"\n\n {STRICT_PROMPT}", user_prompt)
        retry_result = validator(retry)
        if retry_result.valid:
            return SummarizationResult(response=retry, retried=True)

    return SummarizationResult(response=first, retried=True)
