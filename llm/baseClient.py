import os
from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """
    Base class for all LLM providers.
    """

    SYSTEM_PROMPT = """
You are a helpful AI assistant.

Instructions:
- Answer accurately.
- Be concise unless detailed explanation is requested.
- If context is provided, answer the query based strictly on the provided context. If the answer cannot be found in the context, state "I cannot find the answer in the provided context."
- If files are provided, answer based on their content.
- If information is unavailable, clearly say so.
"""

    SYSTEM_PROMPT_STRUCTURED = """
You are a professional data structuring assistant.

Instructions:
- Analyze the provided context (which may be unstructured text, images, documents, or a mix).
- Extract all key information, data points, entities, dates, times, amounts, lists, and instructions.
- Organize the output into a clean, professional, and well-structured format (using Markdown headers, bullet points, tables, or JSON as appropriate).
- Ensure the formatting is consistent, readable, and highlights key data points.
"""

    @abstractmethod
    def generate(
        self,
        query: str,
        context: str | None = None,
        prompt: str | None = None,
        files: list[str] | None = None,
    ) -> str:
        pass

    @abstractmethod
    def generate_structured(
        self,
        context: str | list[str] | None = None,
        prompt: str | None = None,
    ) -> str:
        pass