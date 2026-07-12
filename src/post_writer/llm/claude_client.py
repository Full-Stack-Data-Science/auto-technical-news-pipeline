import anthropic

from post_writer.llm.base import LLMClient
from common.config import Config


class ClaudeClient(LLMClient):
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

    def chat_complete(self, messages, model: str = "claude-haiku-4-5-20251001") -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_messages = [m for m in messages if m["role"] != "system"]

        kwargs = {"model": model, "max_tokens": 1024, "messages": user_messages}
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        return response.content[0].text
