import uuid

class CEOAgent:
    """
    Executive layer responsible for strategic delegation.
    """

    def __init__(self, mission_director, intelligence):
        self.id = str(uuid.uuid4())
        self.director = mission_director
        self.intelligence = intelligence
        self.backlog = []

    def propose(self, capability, description):
        mission = {
            "capability": capability,
            "description": description,
            "status": "planned"
        }

        self.backlog.append(mission)
        return mission

    def prioritize(self):
        return self.backlog

    def execute(self, capability, description):
        return self.director.execute(capability, description)

    def review(self):
        return self.intelligence.analyze()
