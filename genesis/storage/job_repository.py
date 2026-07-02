from .database import Database
from genesis.jobs.job import Job


class JobRepository:

    def __init__(self, database):
        self.db = database

    def add(self, job: Job):
        self.db.cursor.execute(
            """
            INSERT OR REPLACE INTO jobs
            (id, title, description, priority, status, assigned_to)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.title,
                job.description,
                job.priority,
                job.status,
                job.assigned_to,
            ),
        )
        self.db.connection.commit()

        print(f"💾 Saved job: {job.title}")

    def get(self, job_id):
        self.db.cursor.execute(
            "SELECT * FROM jobs WHERE id=?",
            (job_id,),
        )
        return self.db.cursor.fetchone()

    def list(self):
        self.db.cursor.execute("SELECT * FROM jobs")
        return self.db.cursor.fetchall()

    def delete(self, job_id):
        self.db.cursor.execute(
            "DELETE FROM jobs WHERE id=?",
            (job_id,),
        )
        self.db.connection.commit()
