class MissionPlanner:
    """
    Very simple planner.
    Converts a mission into a capability.
    We'll replace this later with an LLM planner.
    """

    RULES = {
        "research": "research",
        "design": "design",
        "architecture": "architecture",
        "python": "python",
        "code": "python",
        "build": "python",
        "test": "testing",
        "qa": "testing",
        "documentation": "documentation",
    }

    def capability_for(self, mission: str):
        mission = mission.lower()

        for word, capability in self.RULES.items():
            if word in mission:
                return capability

        return None
