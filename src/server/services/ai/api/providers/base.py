from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def analyze_bank_statement(self, prompt: str, pdf_bytes: bytes | None = None) -> str:
        """Send prompt (with optional embedded CSV data) and optional PDF bytes, return raw text response."""
        ...
