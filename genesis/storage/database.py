import sqlite3
import threading


class Database:

    def __init__(self, path="genesis.db"):
        self.path = path
        self.lock = threading.RLock()

        self.connection = sqlite3.connect(
            path,
            check_same_thread=False,
        )
        self.connection.row_factory = sqlite3.Row

    def execute(self, sql, params=()):
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute(sql, params)
            self.connection.commit()
            return cursor

    def executescript(self, script):
        with self.lock:
            self.connection.executescript(script)
            self.connection.commit()

    def initialize(self):
        with open("genesis/storage/schema.sql") as f:
            self.executescript(f.read())

        print("💾 Database initialized")

    def close(self):
        with self.lock:
            self.connection.close()
