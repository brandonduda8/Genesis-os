class CapabilityRegistry:
    def __init__(self):
        self.agents = []

    def register(self, agent):
        self.agents.append(agent.profile())

    def all(self):
        return list(self.agents)

    def find_by_skill(self, skill):
        return [
            agent
            for agent in self.agents
            if skill.lower() in
            [s.lower() for s in agent.get("skills", [])]
        ]

    def find_by_tool(self, tool):
        return [
            agent
            for agent in self.agents
            if tool.lower() in
            [t.lower() for t in agent.get("tools", [])]
        ]

    def find_by_role(self, role):
        return [
            agent
            for agent in self.agents
            if role.lower() in agent.get("role", "").lower()
        ]
