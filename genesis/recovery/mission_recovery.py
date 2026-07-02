class MissionRecovery:

    def __init__(self, job_repo, coordinator, executor):
        self.job_repo = job_repo
        self.coordinator = coordinator
        self.executor = executor

    def recover(self):
        print("♻ Checking for unfinished jobs...")

        for job in self.job_repo.pending():
            print(f"🔎 Recovering {job.title}")

            agent = self.coordinator.assign(job)

            if agent is None:
                print(f"⚠ No agent available for {job.title}")
                continue

            result = self.executor.execute(job, agent)

            if result.success:
                print(f"✅ Recovered {job.title}")
            else:
                print(f"❌ Failed recovering {job.title}")
