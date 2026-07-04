class ExecutiveRegistry:
    """
    Registry for executive agents and their capabilities.
    """

    def __init__(self):
        self.executives = {}

    def register(self, agent):
        profile = agent.profile()
        self.executives[profile["name"]] = profile

    def get(self, name):
        return self.executives.get(name)

    def all(self):
        return list(self.executives.values())

    def by_skill(self, skill):
        return [
            executive
            for executive in self.executives.values()
            if skill in executive["skills"]
        ]

    def roles(self):
        return {
            executive["name"]: executive["role"]
            for executive in self.executives.values()
        }
