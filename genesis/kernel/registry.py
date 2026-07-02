from genesis.agents.architect import ArchitectAgent
from genesis.agents.coder import CoderAgent

class AgentRegistry:

    def __init__(self):
        self.agents = {
            "Plan Architecture": ArchitectAgent(),
            "Generate Code": CoderAgent(),
        }

    def get(self, task):
        return self.agents.get(task)
