from genesis.kernel.mission_control import MissionControl

def main():
    print("🚀 Genesis Kernel Booting...")

    mission = input("Mission: ")

    mc = MissionControl()
    mc.run(mission)

if __name__ == "__main__":
    main()
