from origami.engineering.project_inspector import ProjectInspector


class EngineeringMissionGenerator:
    """
    Generates engineering missions based on the
    current state of the Genesis project.
    """

    def generate(self):
        summary = ProjectInspector().summary()
        missions = []

        if summary["todos"] > 0:
            missions.append({
                "priority": "high",
                "title": "Resolve technical debt",
                "reason": (
                    f"{summary['todos']} TODO/FIXME items detected."
                ),
            })

        if summary["markdown_files"] < 10:
            missions.append({
                "priority": "medium",
                "title": "Expand documentation",
                "reason": (
                    "Increase project documentation coverage."
                ),
            })

        missions.append({
            "priority": "low",
            "title": "Review architecture",
            "reason": (
                f"Project currently contains "
                f"{summary['python_files']} Python files."
            ),
        })

        return missions
