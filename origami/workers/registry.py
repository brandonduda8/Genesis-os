class WorkerRegistry:
    def __init__(self):
        self._workers = []

    def register(self, worker):
        self._workers.append(worker)

    def list(self):
        return [w.name for w in self._workers]

    def find(self, capability):
        return [
            w for w in self._workers
            if capability in w.capabilities
        ]

    def best(self, capability):
        workers = self.find(capability)

        if not workers:
            return None

        return max(workers, key=lambda w: w.score(capability))
