from abc import ABC, abstractmethod


class Worker(ABC):
    def __init__(self, name, capabilities=None, priority=50):
        self.name = name
        self.capabilities = capabilities or []
        self.priority = priority

    def available(self):
        return True

    def score(self, capability):
        if capability in self.capabilities:
            return self.priority
        return -1

    @abstractmethod
    def execute(self, mission):
        """Execute a mission."""
        raise NotImplementedError
