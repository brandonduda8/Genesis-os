import uuid


class TeamRegistry:
    """
    Stores and tracks strategic teams and their performance.
    """

    def __init__(self):
        self.teams = {}

    def register(self, name, members):
        team = {
            "id": str(uuid.uuid4()),
            "name": name,
            "members": list(members),
            "missions_completed": 0,
            "missions_failed": 0,
        }

        self.teams[team["id"]] = team
        return team

    def complete_mission(self, team_id):
        if team_id in self.teams:
            self.teams[team_id]["missions_completed"] += 1

    def fail_mission(self, team_id):
        if team_id in self.teams:
            self.teams[team_id]["missions_failed"] += 1

    def all(self):
        return list(self.teams.values())

    def best_team(self):
        if not self.teams:
            return None

        return max(
            self.teams.values(),
            key=lambda team: (
                team["missions_completed"] - team["missions_failed"]
            ),
        )
