class PerformanceEngine:
    """
    Tracks agent and team performance and recommends improvements.
    """

    def __init__(self):
        self.agent_scores = {}
        self.team_scores = {}

    def record_agent(self, name, success=True):
        score = self.agent_scores.setdefault(
            name,
            {"missions": 0, "successes": 0},
        )

        score["missions"] += 1
        if success:
            score["successes"] += 1

    def record_team(self, team_name, success=True):
        score = self.team_scores.setdefault(
            team_name,
            {"missions": 0, "successes": 0},
        )

        score["missions"] += 1
        if success:
            score["successes"] += 1

    def recommend(self):
        return {
            "agents": sorted(
                self.agent_scores.items(),
                key=lambda x: x[1]["successes"],
                reverse=True,
            ),
            "teams": sorted(
                self.team_scores.items(),
                key=lambda x: x[1]["successes"],
                reverse=True,
            ),
        }
