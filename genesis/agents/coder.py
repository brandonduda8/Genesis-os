from genesis.agents.base_agent import BaseAgent

class CoderAgent(BaseAgent):

    name = "Coder"

    def execute(self, task):
        print("💻 Coder generating code...")

        return {
            "agent": self.name,
            "task": task,
            "status": "complete"
        }
