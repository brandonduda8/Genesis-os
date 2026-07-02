from genesis.jobs.job import Job


class JobRepository:

    def __init__(self, database):
        self.db = database

    def add(self, job: Job):
        self.db.execute(
            """
            INSERT INTO jobs
            (id, title, description, priority, status, assigned_agent)
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

        print(f"💾 Saved job: {job.title}")

    def update_status(self, job_id, status):
        self.db.execute(
            """
            UPDATE jobs
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, job_id),
        )

        print(f"🔄 Job {job_id} -> {status}")

    def assign(self, job_id, agent_name):
        self.db.execute(
            """
            UPDATE jobs
            SET assigned_agent = ?,
                status = 'assigned',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (agent_name, job_id),
        )

        print(f"🤖 Assigned {job_id} to {agent_name}")

    def list(self):
        cursor = self.db.execute(
            """
            SELECT *
            FROM jobs
            ORDER BY created_at
            """
        )

        return [tuple(row) for row in cursor.fetchall()]

    def pending(self):
        cursor = self.db.execute(
            """
            SELECT
                id,
                title,
                description,
                priority,
                status,
                assigned_agent
            FROM jobs
            WHERE status != 'completed'
            ORDER BY created_at
            """
        )

        jobs = []

        for row in cursor.fetchall():
            jobs.append(
                Job(
                    id=row[0],
                    title=row[1],
                    description=row[2],
                    priority=row[3],
                    status=row[4],
                    assigned_to=row[5],
                )
            )

        return jobs

    def get(self, job_id):
        cursor = self.db.execute(
            """
            SELECT
                id,
                title,
                description,
                priority,
                status,
                assigned_agent
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return Job(
            id=row[0],
            title=row[1],
            description=row[2],
            priority=row[3],
            status=row[4],
            assigned_to=row[5],
        )

    def is_completed(self, job_id):
        cursor = self.db.execute(
            """
            SELECT status
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        )

        row = cursor.fetchone()

        return row is not None and row[0] == "completed"
