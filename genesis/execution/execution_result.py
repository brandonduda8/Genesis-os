class ExecutionResult:

    def __init__(self, success, output):
        self.success = success
        self.output = output

    def to_dict(self):
        return {
            "success": self.success,
            "output": self.output
        }
