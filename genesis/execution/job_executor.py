from genesis.execution.execution_result import ExecutionResult


class JobExecutor:

    def __init__(self, engine):
        self.engine = engine

    def execute(self, job, agent):
        print(f"▶ Starting job: {job.title}")

        result = self.engine.execute(job, agent)

        print(f"✔ Finished job: {job.title}")

        return ExecutionResult(
            success=result["status"] == "completed",
            output=result["result"],
        )
