class AgentRegistry:

    def __init__(self):
        self.agents = {}

    def register(self, agent):
        self.agents[agent["name"]] = agent
        print(f"🤖 Registered agent: {agent['name']}")

    def get(self, name):
        return self.agents.get(name)

    def list(self):
        return list(self.agents.values())
