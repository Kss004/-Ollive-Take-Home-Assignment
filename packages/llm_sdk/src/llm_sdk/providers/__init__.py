from llm_sdk.providers.base import BaseProvider, ProviderResult
from llm_sdk.providers.openai import OpenAIProvider
from llm_sdk.providers.anthropic import AnthropicProvider
from llm_sdk.providers.gemini import GeminiProvider

__all__ = [
    "BaseProvider",
    "ProviderResult",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "get_provider",
]


def get_provider(name: str) -> BaseProvider:
    name = name.lower()
    if name == "openai":
        return OpenAIProvider()
    if name == "anthropic":
        return AnthropicProvider()
    if name in ("gemini", "google"):
        return GeminiProvider()
    raise ValueError(f"unknown provider: {name}")
