"""Lightweight package boundary shared by Blender and the Job Server."""


def __getattr__(name):
    if name != "server":
        raise AttributeError(name)
    from .app import server

    return server


__all__ = ("server",)
