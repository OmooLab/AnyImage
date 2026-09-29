"""Model adapters selected by the shared catalog."""

from importlib import import_module

from ..model_catalog import get_downloadable_model


def model_adapter(model_key):
    model = get_downloadable_model(model_key)
    return import_module(f".{model.adapter}", __package__)
