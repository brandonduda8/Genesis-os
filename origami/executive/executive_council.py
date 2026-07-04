class ExecutiveCouncil:
    """
    Coordinates executive advisors and gathers recommendations.
    """

    def __init__(self, registry):
        self.registry = registry

    def advise(self, objective):
        recommendations = []

        for executive in self.registry.all():
            recommendations.append({
                "executive": executive["name"],
                "role": executive["role"],
                "focus": executive["skills"][:3],
                "objective": objective,
            })

        return recommendations
