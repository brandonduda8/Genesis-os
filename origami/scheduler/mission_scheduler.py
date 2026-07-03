class MissionScheduler:
    """
    Simple mission scheduler for Genesis.
    """

    def __init__(self):
        self.queue = []

    def submit(self, mission):
        mission.transition("queued")
        self.queue.append(mission)
        return mission.id

    def run_next(self):
        if not self.queue:
            return None

        mission = self.queue.pop(0)

        try:
            mission.transition("running")

            # Placeholder for actual mission execution.
            mission.transition("completed")

        except Exception:
            mission.transition("failed")
            raise

        return mission

    def pending(self):
        return len(self.queue)
