class MissionRepository:

    def __init__(self, database):
        self.db = database

        self.db.cursor.execute("""
        CREATE TABLE IF NOT EXISTS missions (
            id TEXT PRIMARY KEY,
            name TEXT,
            objective TEXT,
            status TEXT,
            progress INTEGER
        )
        """)
        self.db.connection.commit()

    def add(self, mission):
        self.db.cursor.execute(
            """
            INSERT OR REPLACE INTO missions
            (id, name, objective, status, progress)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                mission.id,
                mission.name,
                mission.objective,
                mission.status,
                mission.progress,
            ),
        )
        self.db.connection.commit()

        print(f"🚀 Saved mission: {mission.name}")

    def list(self):
        self.db.cursor.execute("SELECT * FROM missions")
        return self.db.cursor.fetchall()

    def get(self, mission_id):
        self.db.cursor.execute(
            "SELECT * FROM missions WHERE id=?",
            (mission_id,),
        )
        return self.db.cursor.fetchone()

    def delete(self, mission_id):
        self.db.cursor.execute(
            "DELETE FROM missions WHERE id=?",
            (mission_id,),
        )
        self.db.connection.commit()

        print(f"🗑 Deleted mission: {mission_id}")
