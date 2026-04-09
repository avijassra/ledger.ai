import base64

import anthropic

from .base import AIProvider


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def analyze_bank_statement(self, prompt: str, pdf_bytes: bytes | None = None) -> str:
        content = []
        if pdf_bytes is not None:
            content.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf_bytes).decode(),
                },
            })
        content.append({"type": "text", "text": prompt})

        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text
