import os

from .base import AIProvider


def get_ai_provider() -> AIProvider:
    provider = os.getenv("AI_PROVIDER", "gemini").lower()

    if provider == "gemini":
        api_key = os.getenv("AI_API_KEY")
        if not api_key:
            raise EnvironmentError("Gemini API KEY is not configured")
        from .gemini import GeminiProvider
        return GeminiProvider(api_key=api_key)

    if provider == "anthropic":
        api_key = os.getenv("AI_API_KEY")
        if not api_key:
            raise EnvironmentError("Anthropic API KEY is not configured")
        from .anthropic import AnthropicProvider
        return AnthropicProvider(api_key=api_key)

    if provider == "openai":
        api_key = os.getenv("AI_API_KEY")
        if not api_key:
            raise EnvironmentError("OpenAI API KEY is not configured")
        from .openai import OpenAIProvider
        return OpenAIProvider(api_key=api_key)

    raise ValueError(f"Unknown AI_PROVIDER '{provider}'. Choose from: gemini, anthropic, openai")
