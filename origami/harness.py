from origami.registry import AgentRegistry
from origami.router import CapabilityRouter
from origami.planner import MissionPlanner
from origami.executor import MissionExecutor
from origami.status import SystemStatus

from origami.tools.registry import ToolRegistry
from origami.tools.loader import ToolLoader

from origami.memory.store import MemoryStore

from origami.workers.registry import WorkerRegistry
from origami.workers.builder import BuilderWorker
from origami.workers.researcher import ResearchWorker
from origami.workers.design import DesignWorker
from origami.workers.qa import QAWorker


class OrigamiHarness:

    def __init__(self, kernel=None):
        self.kernel = kernel

        self.registry = AgentRegistry()
        self.router = CapabilityRouter(self.registry)

        self.workers = WorkerRegistry()
        self._load_workers()

        self.planner = MissionPlanner()
        self.executor = MissionExecutor(kernel, self)
        self.system = SystemStatus(self)

        self.tools = ToolRegistry()
        ToolLoader.load(self.tools)

        self.memory = MemoryStore()

    def _load_workers(self):
        self.workers.register(BuilderWorker())
        self.workers.register(ResearchWorker())
        self.workers.register(DesignWorker())
        self.workers.register(QAWorker())

    def register(self, name, agent):
        self.registry.register(name, agent)

    def boot(self):
        print("🦢 Origami Harness Online")

        print(f"Registered Agents: {self.registry.count()}")
        print(f"Registered Workers: {len(self.workers.list())}")

        for agent in self.registry.all().values():
            print(
                f" • {agent['name']} "
                f"[{agent['specialty']}] "
                f"({', '.join(agent['capabilities'])})"
            )

        print(f"Registered Tools: {len(self.tools.list())}")

    def route(self, mission):
        capability = self.planner.capability_for(mission)

        if capability is None:
            return {
                "mission": mission,
                "capability": None,
                "agent": None,
            }

        return {
            "mission": mission,
            "capability": capability,
            "agent": self.router.best(capability),
        }

    def execute(self, mission, provider=None):
        self.memory.remember("last_mission", mission)
        return self.executor.execute(mission, provider)

    def remember(self, key, value):
        self.memory.remember(key, value)

    def recall(self, key):
        return self.memory.recall(key)

    def report(self):
        report = self.system.report()
        report["tools"] = self.tools.list()
        report["memory_items"] = len(self.memory.all())
        report["workers"] = self.workers.list()
        return report

    def tools_available(self):
        return self.tools.list()

    def best(self, capability):
        return self.router.best(capability)

    def status(self):
        return self.registry.all()
