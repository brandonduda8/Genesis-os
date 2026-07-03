from origami.memory.mission_store import MissionStore


class MissionHistory:
    """
    Provides read access to persisted mission history.
    """

    def __init__(self):
        self.store = MissionStore()

    def all(self):
        return self.store.all()

    def completed(self):
        return [
            mission
            for mission in self.store.all()
            if mission["status"] == "completed"
        ]

    def pending(self):
        return [
            mission
            for mission in self.store.all()
            if mission["status"] == "queued"
        ]

    def failed(self):
        return [
            mission
            for mission in self.store.all()
            if mission["status"] == "failed"
        ]
