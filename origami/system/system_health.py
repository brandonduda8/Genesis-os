class SystemHealth:

    def __init__(self, genesis):
        self.genesis = genesis

    def check(self):
        return {
            "executives": bool(self.genesis.executives()),
            "knowledge": self.genesis.knowledge is not None,
            "performance": self.genesis.performance is not None,
            "history": len(self.genesis.history_report()),
            "status": "healthy",
        }
