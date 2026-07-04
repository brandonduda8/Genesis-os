from datetime import datetime


class ExecutiveMemory:

    def __init__(self):
        self.records = []

    def remember(self, objective, agent, outcome="success", notes=""):

        self.records.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "objective": objective,
                "agent": agent,
                "outcome": outcome,
                "notes": notes,
            }
        )

    def history(self):
        return list(self.records)
