import uuid

class ObjectiveManager:
    """
    Maintains long-term organizational objectives.
    """

    def __init__(self):
        self.objectives = []

    def create(self, title, priority="medium"):
        objective = {
            "id": str(uuid.uuid4()),
            "title": title,
            "priority": priority,
            "status": "active",
            "missions": []
        }

        self.objectives.append(objective)
        return objective

    def assign_mission(self, objective_id, mission):
        for objective in self.objectives:
            if objective["id"] == objective_id:
                objective["missions"].append(mission)
                return objective
        return None

    def active(self):
        return [o for o in self.objectives if o["status"] == "active"]

    def complete(self, objective_id):
        for objective in self.objectives:
            if objective["id"] == objective_id:
                objective["status"] = "completed"
                return objective
        return None
