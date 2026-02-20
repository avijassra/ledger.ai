import base64

import anthropic

from .base import AIProvider


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def analyze_bank_statement(self, pdf_bytes: bytes, prompt: str) -> str:
        response = self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": base64.standard_b64encode(pdf_bytes).decode(),
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return response.content[0].text
