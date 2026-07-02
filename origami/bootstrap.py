from origami.harness import OrigamiHarness


def build_origami(kernel):
    """
    Build an Origami harness connected to a Genesis kernel.
    """
    harness = OrigamiHarness(kernel)

    repo = kernel.get("agent_repository")

    for row in repo.list():
        name, specialty, capabilities, status, active_jobs = row

        harness.register(
            name,
            {
                "name": name,
                "specialty": specialty,
                "capabilities": [
                    c.strip()
                    for c in capabilities.split(",")
                ],
                "status": status,
                "active_jobs": active_jobs,
            },
        )

    return harness
