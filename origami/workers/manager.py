class WorkerManager:
    def __init__(self, registry):
        self.registry = registry

    def execute(self, capability, mission):
        worker = self.registry.best(capability)

        if worker is None:
            raise RuntimeError(
                f"No worker registered for capability '{capability}'"
            )

        return worker.execute(mission)
