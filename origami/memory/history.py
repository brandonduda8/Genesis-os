from origami.memory.mission_store import MissionStore


class MissionHistory:
    """
    Provides access to persisted mission history.
    """

    def __init__(self):
        self.store = MissionStore()

    def all(self):
        return self.store.all()

    def completed(self):
        return self.by_status("completed")

    def failed(self):
        return self.by_status("failed")

    def pending(self):
        return self.by_status("queued")

    def by_status(self, status):
        return [
            mission
            for mission in self.store.all()
            if mission["status"] == status
        ]

    def by_capability(self, capability):
        return [
            mission
            for mission in self.store.all()
            if mission["capability"] == capability
        ]
