from .kaggle import KaggleProvider
from .colab import ColabProvider
from .modal import ModalProvider
from .lightning import LightningProvider
from .local_s1 import LocalS1Provider


def all_providers() -> dict:
    """provider-name -> provider instance, in stable display order."""
    return {
        "kaggle_gpu": KaggleProvider("gpu"),
        "kaggle_tpu": KaggleProvider("tpu"),
        "colab": ColabProvider(),
        "modal": ModalProvider(),
        "lightning": LightningProvider(),
        "local_s1": LocalS1Provider(),
    }


def get_provider(name: str):
    providers = all_providers()
    if name not in providers:
        raise KeyError(f"unknown provider {name!r}; known: {sorted(providers)}")
    return providers[name]
