from genesis.storage.job_repository import JobRepository


class JobBoard:

    def __init__(self):
        self.repository = JobRepository()

    def add(self, job):
        self.repository.add(job)
        print(f"📌 Job Added: {job.title}")

    def list(self):
        return self.repository.list()

    def get(self, job_id):
        return self.repository.get(job_id)

    def delete(self, job_id):
        self.repository.delete(job_id)
