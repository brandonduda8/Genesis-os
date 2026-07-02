class BaseAgent:

    name = "Base Agent"

    def execute(self, task):
        raise NotImplementedError("Agent must implement execute().")
