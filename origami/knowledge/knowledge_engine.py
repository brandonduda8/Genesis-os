class KnowledgeEngine:
    """
    Learns from mission analytics and recommends future improvements.
    """

    def __init__(self):
        self.best_teams = {}
        self.capability_gaps = set()

    def learn(self, mission_type, team_name, success=True):
        record = self.best_teams.setdefault(
            mission_type,
            {}
        )

        stats = record.setdefault(
            team_name,
            {"missions": 0, "successes": 0}
        )

        stats["missions"] += 1

        if success:
            stats["successes"] += 1

    def report_gap(self, skill):
        self.capability_gaps.add(skill)

    def recommend_team(self, mission_type):
        teams = self.best_teams.get(mission_type, {})

        if not teams:
            return None

        return max(
            teams.items(),
            key=lambda item: item[1]["successes"]
        )[0]

    def summary(self):
        return {
            "best_teams": self.best_teams,
            "capability_gaps": sorted(self.capability_gaps),
        }
