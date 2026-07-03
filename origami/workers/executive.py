from origami.workers.base import Worker


class ExecutiveWorker(Worker):
    """
    Base class for all executive-level workers.

    Provides common reporting, planning, and collaboration
    functionality for Genesis leadership.
    """

    department = "Executive"

    def status(self):
        return {
            "name": self.name,
            "department": self.department,
            "priority": self.priority,
            "capabilities": self.capabilities,
        }

    def report(self):
        return {
            "executive": self.name,
            "department": self.department,
            "health": "healthy",
            "recommendation": "No recommendations.",
        }

    def create_missions(self):
        return []

    def collaborate(self, worker):
        return {
            "from": self.name,
            "to": worker.name,
            "status": "collaboration requested",
        }
