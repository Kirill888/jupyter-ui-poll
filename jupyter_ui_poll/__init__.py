""" Block notebook cells from running while interacting with widgets
"""

from ._poll import ui_poll, with_ui_events

__all__ = (
    "ui_poll",
    "with_ui_events",
)
