import uuid


class StrategicOrchestrator:
    """
    Builds specialized teams of agents for missions.
    """

    def __init__(self):
        self.teams = {}

    def create_team(self, name, members):
        team = {
            "id": str(uuid.uuid4()),
            "name": name,
            "members": list(members),
        }

        self.teams[team["id"]] = team
        return team

    def all_teams(self):
        return list(self.teams.values())

    def recommend_team(self, mission_type):
        recommendations = {
            "engineering": [
                "CTO",
                "Master Engineer",
                "Executive Review",
            ],
            "research": [
                "Research Director",
                "Knowledge Manager",
            ],
            "business": [
                "Business Development",
                "Executive Review",
            ],
        }

        return recommendations.get(mission_type, [])
