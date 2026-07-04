import uuid

from origami.executive.objective_manager import ObjectiveManager
from origami.planning.objective_decomposer import ObjectiveDecomposer


class CEOAgent:
    """
    Executive responsible for pursuing organizational objectives.
    """

    def __init__(self, mission_director, intelligence):
        self.id = str(uuid.uuid4())
        self.director = mission_director
        self.intelligence = intelligence
        self.objectives = ObjectiveManager()

    def pursue(self, objective_title, priority="critical"):
        """
        Pursue a high-level organizational objective by decomposing it
        into executable missions.
        """
        objective = self.objectives.create(objective_title, priority)

        decomposer = ObjectiveDecomposer()
        executions = []

        for capability, description in decomposer.decompose(objective_title):
            result = self.director.execute(capability, description)

            self.objectives.assign_mission(
                objective["id"],
                result["mission"]
            )

            executions.append(result)

        review = self.intelligence.analyze()

        return {
            "objective": objective,
            "executions": executions,
            "review": review,
        }

    def active_objectives(self):
        return self.objectives.active()

    def complete_objective(self, objective_id):
        return self.objectives.complete(objective_id)
