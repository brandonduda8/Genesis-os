import uuid

from origami.analytics.performance_engine import PerformanceEngine
from origami.models.mission import Mission
from origami.orchestration.swarm_builder import SwarmBuilder
from origami.planning.mission_planner import MissionPlanner
from origami.scheduler.mission_scheduler import MissionScheduler


class MissionDirector:
    """
    Plans, staffs, executes, and learns from every mission.
    """

    def __init__(self):
        self.planner = MissionPlanner()
        self.builder = SwarmBuilder()
        self.scheduler = MissionScheduler()
        self.performance = PerformanceEngine()

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

        self.performance.record_team(team["name"])

        for member in team["members"]:
            self.performance.record_agent(member)

        return {
            "execution_id": str(uuid.uuid4()),
            "mission": mission.to_dict(),
            "plan": plan,
            "team": team,
            "analytics": self.performance.recommend(),
        }
