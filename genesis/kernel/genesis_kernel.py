class GenesisKernel:

    def __init__(self):
        self.state = "stopped"

    def boot(self):
        self.state = "running"
        print("🚀 Genesis Kernel Booted")

    def shutdown(self):
        self.state = "stopped"
        print("🛑 Genesis Kernel Shutdown")

    def run(self, mission):
        print(f"🎯 Running mission: {mission}")
