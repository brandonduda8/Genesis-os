from origami.execution.mission_executor import MissionExecutor
from origami.memory.mission_store import MissionStore


class MissionScheduler:
    """
    Schedules and executes missions for Genesis OS.
    """

    def __init__(self):
        self.executor = MissionExecutor()
        self.store = MissionStore()

    def submit(self, mission):
        mission.status = "queued"
        self.store.save(mission)

    def next(self):
        missions = self.store.all()

        queued = [
            mission
            for mission in missions
            if mission["status"] == "queued"
        ]

        if not queued:
            return None

        queued.sort(key=lambda m: m["priority"], reverse=True)

        return queued[0]

    def run_next(self):
        record = self.next()

        if record is None:
            return None

        from origami.models.mission import Mission

        mission = Mission(
            capability=record["capability"],
            description=record["description"],
            priority=record["priority"],
        )

        mission.id = record["id"]
        mission.status = record["status"]
        mission.created_at = record.get("created_at")

        return self.executor.execute(mission)

    def pending(self):
        return len(
            [
                mission
                for mission in self.store.all()
                if mission["status"] == "queued"
            ]
        )
