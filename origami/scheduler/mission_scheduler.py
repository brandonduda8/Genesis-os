class MissionScheduler:
    """
    Schedules and tracks missions for Genesis OS.
    """

    def __init__(self):
        self.queue = []

    def submit(self, mission):
        self.queue.append({
            "mission": mission,
            "status": "queued",
        })

    def next(self):
        if not self.queue:
            return None

        mission = self.queue.pop(0)
        mission["status"] = "running"
        return mission

    def pending(self):
        return len(self.queue)
