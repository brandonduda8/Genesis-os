from datetime import datetime


class ExecutiveMemory:
    def __init__(self):
        self.records = []

    def remember(
        self,
        objective,
        agent,
        outcome="success",
        duration=0,
        notes=None,
    ):
        self.records.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "objective": objective,
                "agent": agent,
                "outcome": outcome,
                "duration": duration,
                "notes": notes or "",
            }
        )

    def history(self):
        return list(self.records)

    def successes(self, agent=None):
        data = self.records
        if agent:
            data = [r for r in data if r["agent"] == agent]
        return [r for r in data if r["outcome"] == "success"]

    def failures(self, agent=None):
        data = self.records
        if agent:
            data = [r for r in data if r["agent"] == agent]
        return [r for r in data if r["outcome"] != "success"]

    def reputation(self):
        summary = {}

        for record in self.records:
            name = record["agent"]

            stats = summary.setdefault(
                name,
                {
                    "missions": 0,
                    "successes": 0,
                    "failures": 0,
                    "average_duration": 0,
                },
            )

            stats["missions"] += 1

            if record["outcome"] == "success":
                stats["successes"] += 1
            else:
                stats["failures"] += 1

            stats["average_duration"] += record["duration"]

        for stats in summary.values():
            if stats["missions"]:
                stats["average_duration"] /= stats["missions"]

        return summary
