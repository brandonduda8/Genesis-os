class ToolManager:

    def __init__(self):
        self.tools = {}

    def register(self, name, tool):
        self.tools[name] = tool

    def available(self):
        return sorted(self.tools.keys())

    def get(self, name):
        return self.tools.get(name)

    def execute(self, name, *args, **kwargs):
        tool = self.get(name)

        if tool is None:
            raise KeyError(name)

        return tool(*args, **kwargs)
