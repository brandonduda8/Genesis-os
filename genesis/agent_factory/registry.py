class AgentRegistry:

    def __init__(self):
        self.agents = {}

    def register(self, agent):
        self.agents[agent.name] = agent

    def get(self, name):
        return self.agents.get(name)

    def list(self):
        return [agent.to_dict() for agent in self.agents.values()]
