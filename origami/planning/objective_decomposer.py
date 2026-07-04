class ObjectiveDecomposer:
    """
    Breaks high-level objectives into executable missions.
    """

    DEFAULT_PLANS = {
        "Build Genesis MVP": [
            ("engineering", "Build executive architecture"),
            ("engineering", "Integrate orchestration systems"),
            ("engineering", "Implement analytics pipeline"),
            ("engineering", "Validate end-to-end workflow"),
        ],
        "Launch Product": [
            ("business", "Create launch strategy"),
            ("marketing", "Prepare marketing assets"),
            ("engineering", "Deploy production release"),
            ("operations", "Monitor launch"),
        ],
    }

    def decompose(self, objective):
        return self.DEFAULT_PLANS.get(
            objective,
            [("general", objective)]
        )
