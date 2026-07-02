class GoalRepository:

    def __init__(self, database):
        self.db = database

        self.db.cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            status TEXT,
            priority TEXT
        )
        """)
        self.db.connection.commit()

    def add(self, goal):
        self.db.cursor.execute(
            """
            INSERT OR REPLACE INTO goals
            (id, title, description, status, priority)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                goal.id,
                goal.title,
                goal.description,
                goal.status,
                goal.priority,
            ),
        )

        self.db.connection.commit()

        print(f"🎯 Saved goal: {goal.title}")

    def list(self):
        self.db.cursor.execute(
            "SELECT * FROM goals"
        )
        return self.db.cursor.fetchall()

    def get(self, goal_id):
        self.db.cursor.execute(
            "SELECT * FROM goals WHERE id=?",
            (goal_id,),
        )
        return self.db.cursor.fetchone()

    def delete(self, goal_id):
        self.db.cursor.execute(
            "DELETE FROM goals WHERE id=?",
            (goal_id,),
        )
        self.db.connection.commit()

        print(f"🗑 Deleted goal: {goal_id}")
