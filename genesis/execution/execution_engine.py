class ExecutionEngine:

    def __init__(self, job_repo, log_repo):
        self.job_repo = job_repo
        self.log_repo = log_repo

    def execute(self, job, agent):
        self.job_repo.assign(job.id, agent.name)
        self.job_repo.update_status(job.id, "running")

        self.log_repo.start(job.id, agent.name)

        print(f"🚀 {agent.name} started: {job.title}")

        result = {
            "status": "completed",
            "result": f"{agent.name} completed {job.title}"
        }

        self.job_repo.update_status(job.id, "completed")

        self.log_repo.finish(
            job.id,
            "completed",
            result["result"]
        )

        print(f"✅ {agent.name} completed: {job.title}")

        return result
