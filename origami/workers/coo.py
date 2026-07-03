from origami.workers.executive import ExecutiveWorker


class COO(ExecutiveWorker):
    """
    Chief Operations Officer.

    Responsible for mission coordination,
    workload balancing, and operational health.
    """

    name = "COO"
    department = "Executive"

    capabilities = [
        "operations",
        "coordination",
        "management",
    ]

    priority = 99

    def execute(self, mission):
        return {
            "success": True,
            "worker": self.name,
            "mission": mission.description,
            "status": "completed",
            "message": "Operations review complete.",
        }

    def report(self):
        report = super().report()

        report["objective"] = (
            "Keep Genesis synchronized and operating efficiently."
        )

        report["recommendation"] = (
            "Review mission queue and balance workloads."
        )

        return report

    def create_missions(self):
        return [
            {
                "title": "Review mission queue",
                "priority": 99,
                "category": "operations",
            },
            {
                "title": "Detect blocked missions",
                "priority": 95,
                "category": "operations",
            },
            {
                "title": "Balance worker workloads",
                "priority": 90,
                "category": "operations",
            },
        ]
