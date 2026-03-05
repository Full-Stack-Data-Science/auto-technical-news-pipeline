from openai import OpenAI

from llm.base import LLMClient
from common.config import Config

class ChatGPTClient(LLMClient):
    def __init__(self):
        self.client = OpenAI(
            base_url=f"{Config.OPENAI_ENDPOINT}",
            api_key=Config.OPENAI_API_KEY
        )
    
    def chat_complete(self, messages, model: str="gpt-4o-mini") -> str:
        response = self.client.chat.completions.create(
            model=model,
            messages=messages
        )

        return response.choices[0].message.content