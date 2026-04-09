from google import genai

from .base import AIProvider


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    def analyze_bank_statement(self, prompt: str, pdf_bytes: bytes | None = None) -> str:
        contents = []
        if pdf_bytes is not None:
            contents.append(genai.types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))
        contents.append(prompt)
        response = self._client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
        )
        return response.text
