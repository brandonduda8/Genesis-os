from genesis.storage.database import Database
from genesis.storage.job_repository import JobRepository
from genesis.storage.agent_repository import AgentRepository
from genesis.storage.goal_repository import GoalRepository
from genesis.storage.mission_repository import MissionRepository


class GenesisKernel:

    def __init__(self):
        self.services = {}
        self.state = "stopped"

    def register(self, name, service):
        self.services[name] = service

    def get(self, name):
        return self.services.get(name)

    def boot(self):
        db = Database()
        db.initialize()

        self.register("database", db)
        self.register("job_repository", JobRepository(db))
        self.register("agent_repository", AgentRepository(db))
        self.register("goal_repository", GoalRepository(db))
        self.register("mission_repository", MissionRepository(db))

        self.state = "running"
        print("🚀 Genesis Kernel Booted")

    def shutdown(self):
        self.state = "stopped"
        print("🛑 Genesis Kernel Shutdown")

    def run(self, mission):
        print(f"🎯 Running mission: {mission}")

    def status(self):
        return {
            "state": self.state,
            "services": list(self.services.keys())
        }
