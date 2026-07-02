class AgentRegistry:
    """
    Central registry for all Origami agents.
    """

    def __init__(self):
        self._agents = {}

    def register(self, name, agent):
        self._agents[name] = agent

    def unregister(self, name):
        self._agents.pop(name, None)

    def get(self, name):
        return self._agents.get(name)

    def all(self):
        return dict(self._agents)

    def names(self):
        return list(self._agents.keys())

    def count(self):
        return len(self._agents)
