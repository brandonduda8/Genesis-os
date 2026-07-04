from abc import ABC, abstractmethod


class ExecutiveAgent(ABC):
    """
    Base class for every executive in Genesis.
    """

    def profile(self):
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "skills": self.skills,
        }

    @abstractmethod
    def plan(self, mission):
        pass

    @abstractmethod
    def execute(self, mission):
        pass

    @abstractmethod
    def review(self, result):
        pass

    @abstractmethod
    def learn(self, outcome):
        pass
