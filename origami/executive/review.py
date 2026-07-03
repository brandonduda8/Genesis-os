class ExecutiveReview:
    """
    Executive Council review of proposed missions.
    """

    def review(self, mission):
        priority = mission.get("priority", "").lower()

        if priority == "high":
            decision = "approved"
            reviewer = "CTO"
        elif priority == "medium":
            decision = "approved"
            reviewer = "COO"
        else:
            decision = "approved"
            reviewer = "CEO"

        return {
            "reviewer": reviewer,
            "decision": decision,
            "mission": mission,
            "notes": "Mission aligns with current Genesis objectives.",
        }
