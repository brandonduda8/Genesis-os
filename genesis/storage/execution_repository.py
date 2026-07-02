from datetime import datetime


class ExecutionRepository:

    def __init__(self, db):
        self.db = db

    def log(self, job_id, agent_name, status, output):
        conn = self.db.connection
        cur = conn.cursor()

        now = datetime.utcnow().isoformat()

        cur.execute(
            """
            INSERT INTO execution_log
            (job_id, agent_name, status, output, started_at, finished_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                agent_name,
                status,
                output,
                now,
                now,
            ),
        )

        conn.commit()

        print(f"📝 Logged execution for {job_id}")
