import uuid

from origami.missions.lifecycle import MissionLifecycle


class Mission:
    """
    Core mission model for Genesis.
    """

    def __init__(self, capability, description, priority=10):
        self.id = str(uuid.uuid4())
        self.capability = capability
        self.description = description
        self.priority = priority

        self.lifecycle = MissionLifecycle()
        self.state = self.lifecycle.state

    def transition(self, new_state):
        self.state = self.lifecycle.transition(new_state)
        return self.state

    def to_dict(self):
        return {
            "id": self.id,
            "capability": self.capability,
            "description": self.description,
            "priority": self.priority,
            "state": self.state,
        }
