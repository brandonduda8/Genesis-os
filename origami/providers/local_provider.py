from origami.providers.provider import Provider
from origami.workers.registry import WorkerRegistry


class LocalProvider(Provider):
    """
    Executes missions using local Genesis workers.
    """

    def __init__(self):
        self.registry = WorkerRegistry()
        self.registry.discover()

    def execute(self, mission):
        worker = self.registry.best(mission.capability)

        if worker is None:
            mission.status = "failed"
            return {
                "success": False,
                "error": f"No worker found for '{mission.capability}'",
            }

        mission.status = "running"

        result = worker.execute(mission.description)

        mission.status = "completed" if result.get("success") else "failed"

        return result
