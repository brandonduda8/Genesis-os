from origami.docs.generator import DocumentationGenerator


class SystemStatus:
    """
    Reports the current status of the Genesis OS runtime.
    """

    def summary(self):
        docs = DocumentationGenerator()
        summary = docs.generate_summary()

        return {
            "version": summary["version"],
            "workers": summary["workers"],
            "providers": summary["providers"],
            "pending_missions": 0,
        }
