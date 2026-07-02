from genesis.jobs.job import Job
import uuid


class MissionPlanner:

    def __init__(self, job_repository):
        self.job_repository = job_repository

    def plan(self, mission):

        research = Job(
            id=str(uuid.uuid4()),
            title="Research",
            description=f"Research: {mission}",
        )

        design = Job(
            id=str(uuid.uuid4()),
            title="Design",
            description=f"Design solution for: {mission}",
            dependencies=[research.id],
        )

        implementation = Job(
            id=str(uuid.uuid4()),
            title="Implementation",
            description=f"Build: {mission}",
            dependencies=[design.id],
        )

        testing = Job(
            id=str(uuid.uuid4()),
            title="Testing",
            description=f"Validate: {mission}",
            dependencies=[implementation.id],
        )

        jobs = [
            research,
            design,
            implementation,
            testing,
        ]

        for job in jobs:
            self.job_repository.add(job)

        print(f"🎯 Mission planned with {len(jobs)} jobs.")

        return jobs
