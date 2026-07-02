from datetime import datetime


class ExecutionLogRepository:

    def __init__(self, database):
        self.db = database

    def start(self, job_id, agent_name):
        self.db.execute(
            """
            INSERT INTO execution_log
            (job_id, agent_name, status, started_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                agent_name,
                "running",
                datetime.utcnow(),
            ),
        )

    def finish(self, job_id, status, output):
        self.db.execute(
            """
            UPDATE execution_log
            SET status = ?,
                output = ?,
                finished_at = ?
            WHERE job_id = ?
            """,
            (
                status,
                output,
                datetime.utcnow(),
                job_id,
            ),
        )

    def list(self):
        cursor = self.db.execute(
            """
            SELECT
                job_id,
                agent_name,
                status,
                started_at,
                finished_at,
                output
            FROM execution_log
            ORDER BY started_at DESC
            """
        )

        return [tuple(row) for row in cursor.fetchall()]
