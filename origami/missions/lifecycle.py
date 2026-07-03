class MissionLifecycle:
    """
    Defines the lifecycle states for Genesis missions.
    """

    STATES = [
        "draft",
        "under_review",
        "approved",
        "queued",
        "running",
        "completed",
        "failed",
        "cancelled",
    ]

    def __init__(self):
        self.state = "draft"

    def transition(self, new_state):
        if new_state not in self.STATES:
            raise ValueError(f"Invalid state: {new_state}")

        self.state = new_state
        return self.state

    def status(self):
        return {
            "current_state": self.state,
            "available_states": self.STATES,
        }
