from IPython import get_ipython
import asyncio
from warnings import warn
import time
import sys


def _replay_events(shell, events):
    kernel = shell.kernel
    sys.stdout.flush()
    sys.stderr.flush()
    for stream, ident, parent in events:
        kernel.set_parent(ident, parent)
        kernel.execute_request(stream, ident, parent)
        if shell._last_traceback is not None:
            # there was an exception drop rest on the floor
            break


def _ui_poll(f, sleep):
    shell = get_ipython()
    kernel = shell.kernel
    events = []
    kernel.shell_handlers['execute_request'] = lambda *e: events.append(e)
    current_parent = (kernel._parent_ident, kernel._parent_header)
    shell.execution_count += 1

    def finalise():
        _replay_events(shell, events)

    try:
        x = f()
        while x is None:
            kernel.do_one_iteration()
            kernel.set_parent(*current_parent
                              )  # ensure stdout still happens in the same cell
            if sleep is not None:
                time.sleep(sleep)
            x = f()
        return x, finalise
    except Exception as e:
        raise e
    finally:
        kernel.shell_handlers['execute_request'] = kernel.execute_request


def ui_poll(f, sleep=0.02):
    """Repeatedly call `f()` until it returns non-None value while also responding to widget events.

    This blocks execution of cells below in the notebook while still preserving
    interactivity of jupyter widgets.
    """

    x, finalise = _ui_poll(f, sleep)
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.call_soon(finalise)
    else:
        warn(
            'Automatic execution of scheduled cells only works with asyncio based ipython'
        )

    return x
