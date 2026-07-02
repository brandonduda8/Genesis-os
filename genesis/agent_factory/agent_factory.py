from genesis.agent_factory.registry import AgentRegistry
from genesis.agent_factory.agent_template import AgentTemplate

from genesis.storage.database import Database
from genesis.storage.agent_repository import AgentRepository


class AgentFactory:

    def __init__(self):
        self.registry = AgentRegistry()

        self.db = Database()
        self.db.initialize()

        self.repo = AgentRepository(self.db)

    def create(self, name, role, skills):
        agent = AgentTemplate(
            name=name,
            role=role,
            skills=skills,
        )

        self.registry.register(agent)
        self.repo.add(agent)

        print(f"🤖 Registered agent: {name}")

        return agent
