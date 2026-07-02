from genesis.kernel.registry import AgentRegistry
from genesis.kernel.orchestrator import Orchestrator
from genesis.memory.memory_engine import MemoryEngine

class MissionControl:

    def __init__(self):
        self.registry = AgentRegistry()
        self.memory = MemoryEngine()
        self.orchestrator = Orchestrator(self.registry)

    def run(self, mission):
        print(f"\nMission Accepted: {mission}")

        tasks = [
            "Plan Architecture",
            "Generate Code"
        ]

        results = self.orchestrator.execute(tasks)

        self.memory.save(mission, results)

        print("\n✅ Mission Complete")
