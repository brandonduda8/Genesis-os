class Scheduler:

    def __init__(self, job_board, registry):
        self.job_board = job_board
        self.registry = registry

    def assign_jobs(self):

        for job in self.job_board.jobs.values():

            if job.status != "queued":
                continue

            matches = self.registry.find_agents(
                job.required_skills
            )

            if matches:
                job.assigned_to = matches[0]
                job.status = "assigned"

                print(
                    f"📌 {job.id} -> {job.assigned_to}"
                )

            else:
                print(
                    f"⚠ No capable agent for {job.id}"
                )
