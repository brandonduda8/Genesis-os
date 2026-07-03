from origami.workers.registry import WorkerRegistry


class ExecutiveCouncil:
    """
    Coordinates executive workers and produces
    a unified executive report.
    """

    def __init__(self):
        self.registry = WorkerRegistry()
        self.registry.discover()

    def executives(self):
        return sorted(
            [
                worker for worker in self.registry._workers
                if getattr(worker, "department", "") == "Executive"
            ],
            key=lambda worker: worker.priority,
            reverse=True,
        )

    def report(self):
        reports = []

        for executive in self.executives():
            reports.append(executive.report())

        return reports

    def recommendation(self):
        return {
            "priority": "HIGH",
            "next_mission": "Build Master Engineer",
            "reason": (
                "Enable safe autonomous code editing, "
                "testing, and continuous improvement."
            ),
        }
