from origami.memory.history import MissionHistory


class MissionStats:
    """
    Computes statistics from mission history.
    """

    def __init__(self):
        self.history = MissionHistory()

    def summary(self):
        missions = self.history.all()

        total = len(missions)
        completed = sum(1 for m in missions if m["status"] == "completed")
        failed = sum(1 for m in missions if m["status"] == "failed")
        queued = sum(1 for m in missions if m["status"] == "queued")

        durations = [
            m.get("duration", 0)
            for m in missions
            if m.get("duration") is not None
        ]

        average_duration = (
            round(sum(durations) / len(durations), 3)
            if durations else 0
        )

        success_rate = (
            round((completed / total) * 100, 2)
            if total else 0
        )

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "queued": queued,
            "success_rate": success_rate,
            "average_duration": average_duration,
        }
