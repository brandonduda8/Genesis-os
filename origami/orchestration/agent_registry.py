class AgentRegistry:
    """
    Registry of all available agents and their capabilities.
    """

    def __init__(self):
        self.agents = []

    def register(self, name, role, skills, capacity=1):
        agent = {
            "name": name,
            "role": role,
            "skills": list(skills),
            "capacity": capacity,
            "status": "available",
            "missions_completed": 0,
        }

        self.agents.append(agent)
        return agent

    def available(self):
        return [
            agent for agent in self.agents
            if agent["status"] == "available"
        ]

    def find_by_skill(self, skill):
        return [
            agent for agent in self.agents
            if skill in agent["skills"]
        ]

    def assign(self, name):
        for agent in self.agents:
            if agent["name"] == name:
                agent["status"] = "busy"
                return agent

    def release(self, name):
        for agent in self.agents:
            if agent["name"] == name:
                agent["status"] = "available"
                agent["missions_completed"] += 1
                return agent

    def all(self):
        return self.agents
