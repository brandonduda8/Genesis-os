from origami.providers.genesis_provider import GenesisProvider


class ProviderLoader:
    """
    Automatically registers all available providers.
    """

    @staticmethod
    def load(kernel, manager):
        manager.register(
            "genesis",
            GenesisProvider(kernel),
        )

        # Future providers:
        #
        # try:
        #     from origami.providers.hermes_provider import HermesProvider
        #     manager.register("hermes", HermesProvider(kernel))
        # except ImportError:
        #     pass
        #
        # try:
        #     from origami.providers.ollama_provider import OllamaProvider
        #     manager.register("ollama", OllamaProvider(kernel))
        # except ImportError:
        #     pass
