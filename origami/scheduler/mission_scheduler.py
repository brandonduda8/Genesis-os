from origami.history.mission_history import MissionHistory


class MissionScheduler:
    """
    Mission scheduler responsible for queueing, executing,
    and recording mission lifecycle events.
    """

    def __init__(self):
        self.queue = []
        self.history = MissionHistory()

    def submit(self, mission):
        mission.transition("queued")
        self.history.record(mission, mission.state)
        self.queue.append(mission)
        return mission.id

    def run_next(self):
        if not self.queue:
            return None

        mission = self.queue.pop(0)

        try:
            mission.transition("running")
            self.history.record(mission, mission.state)

            # Placeholder for actual mission execution.
            # Worker dispatch will be integrated here later.

            mission.transition("completed")
            self.history.record(mission, mission.state)

        except Exception:
            mission.transition("failed")
            self.history.record(mission, mission.state)
            raise

        return mission

    def pending(self):
        return len(self.queue)

    def history_events(self):
        return self.history.all()
