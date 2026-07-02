class ToolRegistry:
    """
    Registry of all tools available to Origami agents.
    """

    def __init__(self):
        self._tools = {}

    def register(self, name, tool):
        self._tools[name] = tool

    def get(self, name):
        return self._tools.get(name)

    def list(self):
        return sorted(self._tools.keys())

    def info(self):
        return {
            name: tool.description
            for name, tool in self._tools.items()
        }
