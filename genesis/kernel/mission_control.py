from genesis.agents.architect import ArchitectAgent
from genesis.agents.coder import CoderAgent
from genesis.memory.memory_engine import MemoryEngine

from genesis.creation_station.blueprint_engine import BlueprintEngine
from genesis.creation_station.project_generator import ProjectGenerator


class MissionControl:

    def __init__(self):
        self.architect = ArchitectAgent()
        self.coder = CoderAgent()
        self.memory = MemoryEngine()

        self.blueprints = BlueprintEngine()
        self.projects = ProjectGenerator()

    def run(self, mission):

        print(f"\nMission Accepted: {mission}\n")

        # Generate project blueprint
        blueprint = self.blueprints.generate(mission)

        # Generate project structure
        project = self.projects.build(blueprint)

        # Run agents
        architect_result = self.architect.execute(mission)
        coder_result = self.coder.execute(mission)

        # Save mission results
        self.memory.save(
            mission,
            {
                "blueprint": blueprint,
                "project": project,
                "architect": architect_result,
                "coder": coder_result,
                "status": "completed"
            }
        )

        print("\n✅ Mission Complete")
