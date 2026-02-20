from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def analyze_bank_statement(self, pdf_bytes: bytes, prompt: str) -> str:
        """Send PDF bytes and prompt, return raw text response from the model."""
        ...
