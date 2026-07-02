from .job import Job

class JobBoard:

    def __init__(self):
        self.jobs = {}

    def add(self, job):
        self.jobs[job.id] = job
        print(f"📌 Job Added: {job.title}")

    def list(self):
        return list(self.jobs.values())

    def claim(self, job_id, agent):
        job = self.jobs.get(job_id)

        if not job:
            return None

        if job.status != "queued":
            return None

        job.status = "running"
        job.assigned_to = agent

        print(f"🤖 {agent} claimed {job.title}")

        return job

    def complete(self, job_id):
        job = self.jobs.get(job_id)

        if job:
            job.status = "completed"
            print(f"✅ {job.title} completed")
