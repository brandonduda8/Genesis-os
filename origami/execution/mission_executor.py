from origami.workers.registry import WorkerRegistry


class MissionExecutor:
    """
    Executes scheduled missions using the best available worker.
    """

    def __init__(self):
        self.registry = WorkerRegistry()
        self.registry.discover()

    def execute(self, capability, mission):
        worker = self.registry.best(capability)

        if worker is None:
            return {
                "success": False,
                "error": f"No worker found for '{capability}'",
            }

        return worker.execute(mission)
