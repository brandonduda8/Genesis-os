from genesis.agents.base_agent import BaseAgent
from genesis.jobs.job import Job


class PlannerAgent(BaseAgent):

    name = "Planner"

    def plan(self, mission):

        print("🧠 Planner breaking mission into jobs...")

        return [
            Job("JOB-001", "Analyze Requirements"),
            Job("JOB-002", "Design Architecture"),
            Job("JOB-003", "Generate Project Structure"),
            Job("JOB-004", "Write Source Code"),
            Job("JOB-005", "Write Tests"),
            Job("JOB-006", "Run Tests"),
            Job("JOB-007", "Review Implementation"),
            Job("JOB-008", "Generate Documentation"),
            Job("JOB-009", "Commit to Git"),
            Job("JOB-010", "Deploy Project"),
        ]
