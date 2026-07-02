class Orchestrator:

    def __init__(self, registry):
        self.registry = registry

    def execute(self, tasks):
        outputs = []

        for task in tasks:
            agent = self.registry.get(task)

            if agent:
                outputs.append(agent.execute(task))
            else:
                outputs.append({
                    "task": task,
                    "status": "no agent"
                })

        return outputs
