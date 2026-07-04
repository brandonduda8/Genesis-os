class DecisionEngine:
    """
    Evaluates executive recommendations and selects
    an execution strategy.
    """

    def decide(self, objective, recommendations):
        return {
            "objective": objective,
            "selected_strategy": recommendations[0] if recommendations else None,
            "participants": [
                r["executive"] for r in recommendations
            ],
            "status": "approved" if recommendations else "pending",
        }
