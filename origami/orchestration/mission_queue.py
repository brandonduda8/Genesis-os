from collections import deque


class MissionQueue:

    def __init__(self):
        self.queue = deque()
        self.records = {}

    def add(self, mission):
        mission = dict(mission)
        mission["state"] = "queued"
        self.queue.append(mission["id"])
        self.records[mission["id"]] = mission
        return mission

    def next(self):
        if not self.queue:
            return None

        mission = self.records[self.queue.popleft()]
        mission["state"] = "assigned"
        return mission

    def update(self, mission_id, state):
        self.records[mission_id]["state"] = state

    def all(self):
        return list(self.records.values())
