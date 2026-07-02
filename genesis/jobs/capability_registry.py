class CapabilityRegistry:

    def __init__(self):
        self.agents = {}

    def register(self, agent_name, skills):
        self.agents[agent_name] = skills

    def find_agents(self, required_skills):
        matches = []

        for agent, skills in self.agents.items():
            if all(skill in skills for skill in required_skills):
                matches.append(agent)

        return matches

    def list_agents(self):
        return self.agents
