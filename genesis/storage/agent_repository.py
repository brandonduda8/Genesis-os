class AgentRepository:

    def __init__(self, database):
        self.db = database

        self.db.cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            name TEXT PRIMARY KEY,
            role TEXT,
            skills TEXT,
            status TEXT,
            jobs_completed INTEGER
        )
        """)
        self.db.connection.commit()

    def add(self, agent):
        self.db.cursor.execute(
            """
            INSERT OR REPLACE INTO agents
            (name, role, skills, status, jobs_completed)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                agent["name"],
                agent["role"],
                ",".join(agent["skills"]),
                agent["status"],
                agent["jobs_completed"],
            ),
        )

        self.db.connection.commit()

        print(f"🤖 Saved agent: {agent['name']}")

    def list(self):
        self.db.cursor.execute("SELECT * FROM agents")
        return self.db.cursor.fetchall()
