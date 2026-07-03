from origami.execution.mission_executor import MissionExecutor
from origami.memory.mission_store import MissionStore


class MissionScheduler:
    """
    Schedules and executes missions for Genesis OS.
    """

    def __init__(self):
        self.queue = []
        self.executor = MissionExecutor()
        self.store = MissionStore()

    def submit(self, mission):
        mission.status = "queued"
        self.queue.append(mission)
        self.store.save(mission)

    def next(self):
        if not self.queue:
            return None

        return self.queue.pop(0)

    def run_next(self):
        mission = self.next()

        if mission is None:
            return None

        result = self.executor.execute(mission)

        # Save updated mission status after execution
        self.store.save(mission)

        return result

    def pending(self):
        return len(self.queue)
