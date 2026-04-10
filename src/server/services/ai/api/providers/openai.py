from openai import OpenAI

from .base import AIProvider


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str):
        self._client = OpenAI(api_key=api_key)

    def analyze_bank_statement(self, prompt: str, pdf_bytes: bytes | None = None) -> str:
        if pdf_bytes is not None:
            file_obj = self._client.files.create(
                file=("statement.pdf", pdf_bytes, "application/pdf"),
                purpose="user_data",
            )
            try:
                response = self._client.responses.create(
                    model="gpt-4o-mini",
                    max_output_tokens=16000,
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
            finally:
                self._client.files.delete(file_obj.id)
        else:
            response = self._client.responses.create(
                model="gpt-4o-mini",
                max_output_tokens=16000,
                input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            )
        return response.output_text
