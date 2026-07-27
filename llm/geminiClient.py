import os
# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
from llm.baseClient import BaseLLMClient


class GeminiClient(BaseLLMClient):

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.6-flash",
    ):
        self.client = genai.Client(
            api_key=api_key or os.getenv("GOOGLE_API_KEY")
        )
        self.model = model

    def generate(
        self,
        query: str,
        context: str | None = None,
        prompt: str | None = None,
        files: list[str] | None = None,
    ) -> str:

        contents = [
            {
                "type": "text",
                "text": prompt or self.SYSTEM_PROMPT,
            }
        ]

        if context:
            contents.append(
                {
                    "type": "text",
                    "text": f"Context:\n{context}\n",
                }
            )

        contents.append(
            {
                "type": "text",
                "text": query,
            }
        )

        if files:
            for path in files:
                uploaded = self.client.files.upload(file=path)

                contents.append(
                    {
                        "type": "file",
                        "uri": uploaded.uri,
                        "mime_type": uploaded.mime_type,
                    }
                )

        response = self.client.interactions.create(
            model=self.model,
            input=contents,
        )

        return response.output_text

    def generate_structured(
        self,
        context: str | list[str] | None = None,
        prompt: str | None = None,
    ) -> str:
        """
        Processes a multimodal context (text strings and/or image/file paths).
        Extracts information and structures it into a clean, well-formatted response.
        """
        contents = [
            {
                "type": "text",
                "text": prompt or self.SYSTEM_PROMPT_STRUCTURED,
            }
        ]

        if context:
            # Normalize context to a list
            context_list = [context] if isinstance(context, str) else context
            
            for item in context_list:
                if isinstance(item, str) and os.path.exists(item):
                    # It's an image/file path: Upload it to Gemini Files API
                    uploaded = self.client.files.upload(file=item)
                    contents.append(
                        {
                            "type": "file",
                            "uri": uploaded.uri,
                            "mime_type": uploaded.mime_type,
                        }
                    )
                else:
                    # It's plain text context
                    contents.append(
                        {
                            "type": "text",
                            "text": f"Context Content:\n{item}\n",
                        }
                    )

        response = self.client.interactions.create(
            model=self.model,
            input=contents,
        )

        return response.output_text