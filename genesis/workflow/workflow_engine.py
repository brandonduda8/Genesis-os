from genesis.jobs.scheduler import Scheduler


class WorkflowEngine:

    def __init__(self, planner, job_board, registry):
        self.planner = planner
        self.job_board = job_board
        self.registry = registry
        self.scheduler = Scheduler(job_board, registry)

    def run(self, mission):

        print(f"\n🚀 Starting Workflow: {mission}")

        cycle = 1

        while True:

            print(f"\n🔄 Cycle {cycle}")

            # Let the planner create additional work
            self.planner.plan(mission, self.job_board)

            # Assign queued jobs
            self.scheduler.assign_jobs()

            unfinished = [
                job for job in self.job_board.list()
                if job.status != "completed"
            ]

            if not unfinished:
                print("\n✅ Workflow Complete")
                break

            for job in unfinished:

                print(
                    f"🤖 Executing {job.id}: {job.title}"
                )

                job.status = "completed"

            cycle += 1
