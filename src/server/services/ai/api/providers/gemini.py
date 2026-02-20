from google import genai

from .base import AIProvider


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    def analyze_bank_statement(self, pdf_bytes: bytes, prompt: str) -> str:
        response = self._client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                genai.types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                prompt,
            ],
        )
        return response.text
