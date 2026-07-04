from origami.executive.agent_x import AgentX
from origami.executive.agent_json import AgentJSON
from origami.executive.executive_registry import ExecutiveRegistry
from origami.executive.executive_council import ExecutiveCouncil
from origami.executive.decision_engine import DecisionEngine

from origami.orchestration.mission_director import MissionDirector
from origami.orchestration.swarm_builder import SwarmBuilder
from origami.planning.mission_planner import MissionPlanner

from origami.knowledge.knowledge_engine import KnowledgeEngine
from origami.analytics.performance_engine import PerformanceEngine
from origami.intelligence.strategic_intelligence import StrategicIntelligence

from origami.history.mission_history import MissionHistory
from origami.history.persistence import Persistence


class Genesis:
    """
    Genesis Operating System
    """

    def __init__(self):
        self.persistence = Persistence()
        self.saved_state = self.persistence.load()

        self.knowledge = KnowledgeEngine()
        self.performance = PerformanceEngine()
        self.intelligence = StrategicIntelligence(self.knowledge)

        self.director = MissionDirector()
        self.planner = MissionPlanner()
        self.swarm = SwarmBuilder()

        self.history = MissionHistory()

        for record in self.saved_state.get("history", []):
            self.history.history.append(record)

        self.registry = ExecutiveRegistry()

        self.agent_x = AgentX(
            self.director,
            self.planner,
            self.swarm,
            self.knowledge,
            self.performance,
            self.intelligence,
        )

        self.agent_json = AgentJSON()

        self.registry.register(self.agent_x)
        self.registry.register(self.agent_json)

        self.council = ExecutiveCouncil(self.registry)
        self.decision_engine = DecisionEngine()

    def executives(self):
        return self.registry.roles()

    def advise(self, objective):
        return self.council.advise(objective)

    def decide(self, objective):
        advice = self.advise(objective)

        decision = self.decision_engine.decide(
            objective,
            advice,
        )

        self.history.record(objective, decision)

        # Learn from every decision
        self.knowledge.learn(
            "executive",
            decision["selected_strategy"]["executive"],
        )

        self.performance.record_agent(
            decision["selected_strategy"]["executive"]
        )

        return decision

    def strategic_review(self):
        return self.intelligence.analyze()

    def save(self):
        self.persistence.save(
            {
                "history": self.history.all(),
                "executives": self.registry.roles(),
            }
        )

    def history_report(self):
        return self.history.all()

    def status(self):
        return {
            "executives": self.registry.roles(),
            "missions_completed": self.history.count(),
            "knowledge": self.knowledge.summary(),
            "performance": self.performance.recommend(),
        }
