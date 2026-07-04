class StrategicIntelligence:
    """
    Converts organizational knowledge into strategic recommendations.
    """

    def __init__(self, knowledge):
        self.knowledge = knowledge

    def analyze(self):
        summary = self.knowledge.summary()

        recommendations = []

        for skill in summary["capability_gaps"]:
            recommendations.append(
                f"Recruit or create an agent specializing in '{skill}'."
            )

        for mission_type, teams in summary["best_teams"].items():
            best = max(
                teams.items(),
                key=lambda item: item[1]["successes"]
            )[0]

            recommendations.append(
                f"Use '{best}' as the preferred team for {mission_type} missions."
            )

        return {
            "knowledge": summary,
            "recommendations": recommendations,
        }
