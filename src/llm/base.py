from abc import ABC, abstractclassmethod

class LLMClient(ABC):
    @abstractclassmethod
    def chat_complete(self, message, model: str) -> str:
        pass

    