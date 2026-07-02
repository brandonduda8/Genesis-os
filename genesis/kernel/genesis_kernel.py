from concurrent.futures import ThreadPoolExecutor

from genesis.storage.database import Database
from genesis.storage.job_repository import JobRepository
from genesis.storage.agent_repository import AgentRepository
from genesis.storage.goal_repository import GoalRepository
from genesis.storage.mission_repository import MissionRepository
from genesis.storage.execution_log_repository import ExecutionLogRepository

from genesis.planning.mission_planner import MissionPlanner
from genesis.coordinator.coordinator import Coordinator

from genesis.execution.execution_engine import ExecutionEngine
from genesis.execution.job_executor import JobExecutor

from genesis.recovery.mission_recovery import MissionRecovery


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

        job_repo = JobRepository(db)
        agent_repo = AgentRepository(db)
        goal_repo = GoalRepository(db)
        mission_repo = MissionRepository(db)
        log_repo = ExecutionLogRepository(db)

        planner = MissionPlanner(job_repo)
        coordinator = Coordinator(agent_repo)

        engine = ExecutionEngine(job_repo, log_repo)
        executor = JobExecutor(engine)

        recovery = MissionRecovery(
            job_repo,
            coordinator,
            executor,
        )

        self.register("database", db)
        self.register("job_repository", job_repo)
        self.register("agent_repository", agent_repo)
        self.register("goal_repository", goal_repo)
        self.register("mission_repository", mission_repo)
        self.register("execution_log_repository", log_repo)

        self.register("planner", planner)
        self.register("coordinator", coordinator)
        self.register("execution_engine", engine)
        self.register("job_executor", executor)
        self.register("mission_recovery", recovery)

        self.state = "running"

        print("🚀 Genesis Kernel Booted")

        recovery.recover()

    def shutdown(self):
        self.state = "stopped"
        print("🛑 Genesis Kernel Shutdown")

    def status(self):
        return {
            "state": self.state,
            "services": list(self.services.keys()),
        }

    def run(self, mission):
        print(f"🎯 Running mission: {mission}")

        planner = self.get("planner")
        coordinator = self.get("coordinator")
        executor = self.get("job_executor")
        repo = self.get("job_repository")

        jobs = planner.plan(mission)

        for job in jobs:

            if any(
                not repo.is_completed(dep)
                for dep in job.dependencies
            ):
                print(f"⏸ Waiting for dependencies: {job.title}")
                continue

            agent = coordinator.assign(job)

            if agent is None:
                print(f"⚠ No agent available for {job.title}")
                continue

            result = executor.execute(job, agent)

            if result.success:
                print(f"✅ {job.title} completed.")
            else:
                print(f"❌ {job.title} failed.")

        print("🏁 Mission complete.")
