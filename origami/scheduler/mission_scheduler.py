from origami.execution.mission_executor import MissionExecutor


class MissionScheduler:
    """
    Queues and executes Mission objects.
    """

    def __init__(self):
        self.queue = []
        self.executor = MissionExecutor()

    def submit(self, mission):
        mission.status = "queued"
        self.queue.append(mission)

    def run_next(self):
        if not self.queue:
            return None

        mission = self.queue.pop(0)
        return self.executor.execute(mission)

    def pending(self):
        return len(self.queue)
