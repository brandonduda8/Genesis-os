import uuid


class MissionRepository:

    def __init__(self, database):
        self.db = database

    def add(self, mission, status="planned"):
        mission_id = getattr(mission, "id", str(uuid.uuid4()))
        mission_name = getattr(mission, "name", str(mission))

        self.db.execute(
            """
            INSERT INTO missions
            (id, mission, status)
            VALUES (?, ?, ?)
            """,
            (
                mission_id,
                mission_name,
                status,
            ),
        )

        print(f"🚀 Saved mission: {mission_name}")

    def list(self):
        cursor = self.db.execute(
            """
            SELECT id, mission, status, created_at
            FROM missions
            ORDER BY created_at DESC
            """
        )
        return [tuple(row) for row in cursor.fetchall()]

    def get(self, mission_id):
        cursor = self.db.execute(
            """
            SELECT id, mission, status, created_at
            FROM missions
            WHERE id = ?
            """,
            (mission_id,),
        )
        row = cursor.fetchone()
        return tuple(row) if row else None

    def delete(self, mission_id):
        self.db.execute(
            """
            DELETE FROM missions
            WHERE id = ?
            """,
            (mission_id,),
        )

        print(f"🗑 Deleted mission: {mission_id}")
