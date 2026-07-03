from abc import ABC, abstractmethod


class Worker(ABC):
    """
    Base class for all Genesis OS workers.
    Workers expose metadata through class attributes so they
    can be discovered automatically by the WorkerRegistry.
    """

    name = "Worker"
    capabilities = []
    priority = 50

    def __init__(self):
        pass

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
