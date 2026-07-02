from genesis.agent_factory.registry import AgentRegistry

class AgentFactory:

    def __init__(self):
        self.registry = AgentRegistry()

    def create(
        self,
        name,
        role,
        skills,
        tools=None
    ):
        agent = {
            "name": name,
            "role": role,
            "skills": skills,
            "tools": tools or [],
            "status": "idle",
            "jobs_completed": 0
        }

        self.registry.register(agent)

        return agent
