from contextlib import contextmanager
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
        if kernel._aborting:
            kernel._send_abort_reply(stream, parent, ident)
        else:
            kernel.execute_request(stream, ident, parent)


@contextmanager
def ui_events():
    """ Gives you a function you can call to process ui events while running a long
    task inside a Jupyter cell.


    .. code-block: python
       with ui_events() as ui_poll:
          while some_condition:
             ui_poll(10)  # Process upto 10 UI events if any happened
             do_some_more_compute()


    - Delay processing `execute_request` IPython kernel events
    - Calls `kernel.do_one_iteration()`
    - Schedule replay of any blocked `execute_request` events upon
      exiting from the context manager
    """

    shell = get_ipython()
    kernel = shell.kernel
    events = []
    kernel.shell_handlers['execute_request'] = lambda *e: events.append(e)
    current_parent = (kernel._parent_ident, kernel._parent_header)

    # shell.execution_count += 1

    def poll(n=1):
        for _ in range(n):
            # ensure stdout still happens in the same cell
            kernel.set_parent(*current_parent)
            kernel.do_one_iteration()
            kernel.set_parent(*current_parent)

    try:
        poll()  # ensure poll is called at least once to correct output redirect
        yield poll
    finally:
        kernel.shell_handlers['execute_request'] = kernel.execute_request
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon(lambda: _replay_events(shell, events))
        else:
            warn(
                'Automatic execution of scheduled cells only works with asyncio based ipython'
            )


def with_ui_events(its, n=1):
    """ Deal with kernel ui events while processing a long sequence

    :param its: Iterator to pass through
    :param n:   Number of events to process in between items

    - Delay processing `execute_request` IPython kernel events
    - Inject calls to `kernel.do_one_iteration()` in between iterations
    - Schedule replay of any blocked `execute_request` events when data sequence is exhausted
    """
    with ui_events() as poll:
        try:
            for x in its:
                poll(n)
                yield x
        except GeneratorExit:
            pass
        except Exception as e:
            raise e


def run_ui_poll_loop(f, sleep=0.02, n=1):
    """Repeatedly call `f()` until it returns non-None value while also responding to widget events.

    This blocks execution of cells below in the notebook while still preserving
    interactivity of jupyter widgets.

    :param f: Function to periodically call (`f()` should not block for long)
    :param sleep: Amount of time to sleep in between polling (in seconds, 1/50 is the default)
    :param n: Number of events to process per iteration

    Returns
    =======
    First non-None value returned from `f()`
    """
    def as_iterator(f, sleep):
        x = None
        while x is None:
            if sleep is not None:
                time.sleep(sleep)

            x = f()
            yield x

    for x in with_ui_events(as_iterator(f, sleep), n):
        if x is not None:
            return x
