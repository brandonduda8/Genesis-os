import uuid


class GoalRepository:

    def __init__(self, database):
        self.db = database

    def add(self, title, description="", status="active"):
        goal_id = str(uuid.uuid4())

        self.db.execute(
            """
            INSERT INTO goals
            (id, title, description, status)
            VALUES (?, ?, ?, ?)
            """,
            (
                goal_id,
                title,
                description,
                status,
            ),
        )

        return goal_id

    def update_status(self, goal_id, status):
        self.db.execute(
            """
            UPDATE goals
            SET status = ?
            WHERE id = ?
            """,
            (
                status,
                goal_id,
            ),
        )

    def list(self):
        cursor = self.db.execute(
            """
            SELECT
                id,
                title,
                description,
                status
            FROM goals
            ORDER BY title
            """
        )

        return [tuple(row) for row in cursor.fetchall()]
