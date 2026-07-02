class ProjectGenerator:
    """
    Generates the initial project structure from a blueprint.
    """

    def build(self, blueprint: dict):
        print(f"🏗 Creating project: {blueprint['project_name']}")

        for task in blueprint["tasks"]:
            print(f"   • {task}")

        return {
            "status": "project_generated",
            "project": blueprint["project_name"]
        }
