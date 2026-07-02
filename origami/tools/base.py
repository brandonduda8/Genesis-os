class Tool:
    """
    Base class for all Origami tools.
    """

    name = "tool"
    description = "Base tool"

    def run(self, *args, **kwargs):
        raise NotImplementedError("Tool must implement run().")
