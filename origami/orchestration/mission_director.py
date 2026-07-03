import uuid

from origami.models.mission import Mission
from origami.planning.mission_planner import MissionPlanner
from origami.orchestration.swarm_builder import SwarmBuilder
from origami.scheduler.mission_scheduler import MissionScheduler


class MissionDirector:
    """
    Coordinates planning, team assembly, and execution.
    """

    def __init__(self):
        self.planner = MissionPlanner()
        self.builder = SwarmBuilder()
        self.scheduler = MissionScheduler()

    def register_agent(self, name, role, skills, capacity=1):
        return self.builder.register_agent(name, role, skills, capacity)

    def execute(self, capability, description, priority=100):
        plan = self.planner.plan(description)

        team = self.builder.build(
            f"{capability.title()} Team",
            plan["skills"],
        )

        mission = Mission(
            capability,
            description,
            priority,
        )

        self.scheduler.submit(mission)
        self.scheduler.run_next()

        self.builder.complete(team["id"])

        return {
            "execution_id": str(uuid.uuid4()),
            "mission": mission.to_dict(),
            "plan": plan,
            "team": team,
        }
