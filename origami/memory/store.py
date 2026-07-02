class MemoryStore:
    """
    Simple in-memory knowledge store.
    Can later be backed by SQLite or a vector database.
    """

    def __init__(self):
        self._memory = {}

    def remember(self, key, value):
        self._memory[key] = value

    def recall(self, key, default=None):
        return self._memory.get(key, default)

    def forget(self, key):
        self._memory.pop(key, None)

    def all(self):
        return dict(self._memory)

    def clear(self):
        self._memory.clear()
