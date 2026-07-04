class CapabilityMatcher:
    def __init__(self, registry):
        self.registry = registry

    def rank(self, required_skills):
        scored = []

        for agent in self.registry.all():
            score = sum(
                1
                for skill in required_skills
                if skill.lower() in
                [s.lower() for s in agent.get("skills", [])]
            )

            scored.append(
                {
                    "agent": agent["name"],
                    "role": agent["role"],
                    "score": score,
                    "skills": agent["skills"],
                }
            )

        return sorted(
            scored,
            key=lambda x: x["score"],
            reverse=True,
        )

    def best(self, required_skills):
        ranked = self.rank(required_skills)
        return ranked[0] if ranked else None
