import uuid
from datetime import datetime


class MissionHistory:
    """
    Stores completed executive decisions and mission executions.
    """

    def __init__(self):
        self.history = []

    def record(self, objective, decision, execution=None):
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "objective": objective,
            "decision": decision,
            "execution": execution,
        }

        self.history.append(entry)
        return entry

    def latest(self):
        return self.history[-1] if self.history else None

    def all(self):
        return list(self.history)

    def count(self):
        return len(self.history)

    def clear(self):
        self.history.clear()
