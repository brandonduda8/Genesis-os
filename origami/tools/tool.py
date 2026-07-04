from abc import ABC, abstractmethod


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def capabilities(self) -> list[str]:
        pass

    @abstractmethod
    def execute(self, task: dict) -> dict:
        pass
