from uuid import uuid4

from genesis.jobs.job import Job


class MissionPlanner:

    def __init__(self):
        pass

    def plan(self, objective):
        """
        Convert a high-level objective into executable jobs.
        """

        return [
            Job(
                id=str(uuid4()),
                title="Research",
                description=f"Research: {objective}"
            ),
            Job(
                id=str(uuid4()),
                title="Design",
                description=f"Design solution for: {objective}"
            ),
            Job(
                id=str(uuid4()),
                title="Implementation",
                description=f"Build: {objective}"
            ),
            Job(
                id=str(uuid4()),
                title="Testing",
                description=f"Validate: {objective}"
            ),
        ]
