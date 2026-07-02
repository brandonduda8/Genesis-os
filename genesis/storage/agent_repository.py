class AgentRepository:

    def __init__(self, database):
        self.db = database

    def add(self, agent):
        self.db.execute(
            """
            INSERT OR REPLACE INTO agents
            (name, role, skills, status, jobs_completed)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                agent.name,
                agent.role,
                ",".join(agent.skills),
                getattr(agent, "status", "idle"),
                getattr(agent, "jobs_completed", 0),
            ),
        )

        print(f"🤖 Saved agent: {agent.name}")

    def list(self):
        cursor = self.db.execute(
            """
            SELECT
                name,
                role,
                skills,
                status,
                jobs_completed
            FROM agents
            ORDER BY name
            """
        )

        return [tuple(row) for row in cursor.fetchall()]

    def available(self):
        cursor = self.db.execute(
            """
            SELECT
                name,
                role,
                skills,
                status,
                jobs_completed
            FROM agents
            WHERE status = 'idle'
            ORDER BY name
            """
        )

        return [tuple(row) for row in cursor.fetchall()]

    def update_status(self, name, status):
        self.db.execute(
            """
            UPDATE agents
            SET status = ?
            WHERE name = ?
            """,
            (status, name),
        )
