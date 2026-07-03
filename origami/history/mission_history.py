from datetime import datetime


class MissionHistory:
    """
    Records mission lifecycle events.
    """

    def __init__(self):
        self.events = []

    def record(self, mission, state):
        event = {
            "mission_id": mission.id,
            "state": state,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self.events.append(event)
        return event

    def all(self):
        return list(self.events)
