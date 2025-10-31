"""Block notebook cells from running while interacting with widgets"""

from ._poll import ui_events, with_ui_events, run_ui_poll_loop

__all__ = (
    "ui_events",
    "with_ui_events",
    "run_ui_poll_loop",
)


def __dir__():
    return [*__all__, "__version__"]


def __getattr__(name):
    # pylint: disable=import-outside-toplevel
    if name == "__version__":
        from importlib.metadata import version

        return version(__name__)
    raise AttributeError(f"module {__name__} has no attribute {name}")
