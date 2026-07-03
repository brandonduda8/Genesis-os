from origami.memory.history import MissionHistory


class MissionQueue:
    """
    Provides access to queued missions.
    """

    def __init__(self):
        self.history = MissionHistory()

    def all(self):
        return self.history.pending()

    def count(self):
        return len(self.all())

    def empty(self):
        return self.count() == 0
