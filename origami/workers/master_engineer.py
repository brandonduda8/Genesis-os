from origami.workers.base import Worker
from origami.engineering.project_inspector import ProjectInspector


class MasterEngineer(Worker):
    """
    Master Engineer

    Coordinates engineering work and continuously
    improves the Genesis platform.
    """

    name = "Master Engineer"

    capabilities = [
        "engineering",
        "architecture",
        "python",
        "testing",
        "refactoring",
        "code_review",
    ]

    priority = 95

    def review(self):
        return {
            "worker": self.name,
            "health": "healthy",
            "objective": (
                "Continuously improve the Genesis codebase."
            ),
        }

    def report(self):
        summary = ProjectInspector().summary()

        if summary["todos"] == 0:
            recommendation = (
                "Continue expanding Genesis capabilities."
            )
        elif summary["todos"] < 5:
            recommendation = (
                "Resolve remaining TODO items before major expansion."
            )
        else:
            recommendation = (
                "Prioritize technical debt reduction."
            )

        return {
            "worker": self.name,
            "python_files": summary["python_files"],
            "markdown_files": summary["markdown_files"],
            "workers": summary["workers"],
            "executives": summary["executives"],
            "technical_debt_items": summary["todos"],
            "recommendation": recommendation,
        }

    def create_missions(self):
        return [
            {
                "title": "Review project architecture",
                "priority": "high",
            },
            {
                "title": "Increase automated test coverage",
                "priority": "medium",
            },
        ]

    def execute(self, mission):
        return {
            "status": "completed",
            "worker": self.name,
            "mission": mission,
            "result": (
                "Engineering analysis complete. "
                "Recommendations generated."
            ),
        }
