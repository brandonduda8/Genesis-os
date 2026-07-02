import sys
from genesis.kernel.mission_control import MissionControl

def main():
    print("🚀 Genesis Kernel Booting...")

    if len(sys.argv) > 1:
        mission = " ".join(sys.argv[1:])
    else:
        mission = input("Mission: ")

    controller = MissionControl()
    controller.run(mission)

if __name__ == "__main__":
    main()
