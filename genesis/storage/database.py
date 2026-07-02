import sqlite3

class Database:

    def __init__(self, path="genesis.db"):
        self.connection = sqlite3.connect(path)
        self.cursor = self.connection.cursor()

    def initialize(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            priority TEXT,
            status TEXT,
            assigned_to TEXT
        )
        """)

        self.connection.commit()
        print("💾 Database initialized")

    def close(self):
        self.connection.close()
