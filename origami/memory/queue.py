from origami.memory.history import MissionHistory
from origami.memory.mission_store import MissionStore


class MissionQueue:
    """
    Provides access to queued missions.
    """

    def __init__(self):
        self.history = MissionHistory()
        self.store = MissionStore()

    def all(self):
        return self.history.pending()

    def count(self):
        return len(self.all())

    def empty(self):
        return self.count() == 0

    def cancel(self, mission_id):
        missions = self.store.all()

        for mission in missions:
            if mission["id"] == mission_id:
                if mission["status"] != "queued":
                    return False

                mission["status"] = "cancelled"
                self.store.save_all(missions)
                return True

        return False

    def update_priority(self, mission_id, priority):
        missions = self.store.all()

        for mission in missions:
            if mission["id"] == mission_id:
                if mission["status"] != "queued":
                    return False

                mission["priority"] = priority
                self.store.save_all(missions)
                return True

        return False
