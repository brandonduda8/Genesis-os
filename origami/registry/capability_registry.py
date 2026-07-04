class CapabilityRegistry:
    def __init__(self):
        self._agents = {}

    def register(self, agent):
        profile = agent.profile()
        self._agents[profile["name"]] = profile

    def agents(self):
        return list(self._agents.values())

    def names(self):
        return sorted(self._agents.keys())

    def by_role(self, role):
        return [
            a for a in self._agents.values()
            if a["role"] == role
        ]

    def by_skill(self, skill):
        return [
            a for a in self._agents.values()
            if skill in a.get("skills", [])
        ]

    def by_tool(self, tool):
        return [
            a for a in self._agents.values()
            if tool in a.get("tools", [])
        ]

    def recommend(self, required_skills):
        ranked = []

        for agent in self._agents.values():
            skills = set(agent.get("skills", []))
            score = len(skills.intersection(required_skills))
            if score:
                ranked.append((score, agent))

        ranked.sort(key=lambda x: x[0], reverse=True)

        return [agent for _, agent in ranked]
