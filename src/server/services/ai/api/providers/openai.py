from openai import OpenAI

from .base import AIProvider


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = OpenAI(api_key=api_key)

    def analyze_bank_statement(self, pdf_bytes: bytes, prompt: str) -> str:
        # Upload PDF to Files API, use the returned file_id, then clean up
        file_obj = self._client.files.create(
            file=("statement.pdf", pdf_bytes, "application/pdf"),
            purpose="user_data",
        )
        try:
            response = self._client.responses.create(
                model="gpt-4o",
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_file", "file_id": file_obj.id},
                            {"type": "input_text", "text": prompt},
                        ],
                    }
                ],
            )
            return response.output_text
        finally:
            self._client.files.delete(file_obj.id)
