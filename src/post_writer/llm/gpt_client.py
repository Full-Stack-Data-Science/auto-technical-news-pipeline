from openai import OpenAI

from post_writer.llm.base import LLMClient
from common.config import Config

class ChatGPTClient(LLMClient):
    def __init__(self):
        kwargs = {"api_key": Config.OPENAI_API_KEY}
        if Config.OPENAI_ENDPOINT:
            kwargs["base_url"] = Config.OPENAI_ENDPOINT
        self.client = OpenAI(**kwargs)
    
    def chat_complete(self, messages, model: str="gpt-4o-mini") -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=messages
        )

        return response.choices[0].message.content