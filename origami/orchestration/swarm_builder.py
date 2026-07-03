import uuid

from origami.orchestration.agent_registry import AgentRegistry
from origami.orchestration.team_registry import TeamRegistry


class SwarmBuilder:
    """
    Builds mission-specific teams from registered agents.
    """

    def __init__(self):
        self.agents = AgentRegistry()
        self.teams = TeamRegistry()

    def register_agent(self, name, role, skills, capacity=1):
        return self.agents.register(name, role, skills, capacity)

    def build(self, team_name, required_skills):
        selected = []
        used = set()

        for skill in required_skills:
            candidates = self.agents.find_by_skill(skill)

            for agent in candidates:
                if (
                    agent["status"] == "available"
                    and agent["name"] not in used
                ):
                    selected.append(agent)
                    used.add(agent["name"])
                    self.agents.assign(agent["name"])
                    break

        team = self.teams.register(
            team_name,
            [agent["name"] for agent in selected],
        )

        return team

    def complete(self, team_id):
        self.teams.complete_mission(team_id)

        team = next(
            t for t in self.teams.all()
            if t["id"] == team_id
        )

        for member in team["members"]:
            self.agents.release(member)

        return team
