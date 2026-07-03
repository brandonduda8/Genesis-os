class MissionPlanner:
    """
    Converts a mission into the capabilities required to execute it.
    """

    def __init__(self):
        self.rules = {
            "technical debt": {
                "skills": [
                    "architecture",
                    "python",
                    "testing",
                    "review",
                ],
                "priority": "high",
            },
            "documentation": {
                "skills": [
                    "documentation",
                    "writing",
                ],
                "priority": "medium",
            },
            "architecture": {
                "skills": [
                    "architecture",
                    "leadership",
                ],
                "priority": "low",
            },
        }

    def plan(self, mission):
        text = mission.lower()

        for keyword, plan in self.rules.items():
            if keyword in text:
                return {
                    "mission": mission,
                    "skills": plan["skills"],
                    "priority": plan["priority"],
                    "estimated_team_size": len(plan["skills"]),
                }

        return {
            "mission": mission,
            "skills": [],
            "priority": "low",
            "estimated_team_size": 0,
        }
