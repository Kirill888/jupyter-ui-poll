import asyncio
import sys
import time
from contextlib import contextmanager

import zmq
from IPython import get_ipython
from tornado.queues import QueueEmpty


async def _replay_events(kernel, events):
    sys.stdout.flush()
    sys.stderr.flush()
    for stream, ident, parent in events:
        kernel.set_parent(ident, parent)
        if kernel._aborting:
            kernel._send_abort_reply(stream, parent, ident)
        else:
            await kernel.execute_request(stream, ident, parent)
            # replicate shell_dispatch behaviour
            sys.stdout.flush()
            sys.stderr.flush()
            kernel._publish_status('idle', 'shell')
            kernel.shell_stream.flush(zmq.POLLOUT)


@contextmanager
def ui_events():
    """
    Gives you a async function you can call to process ui events while running a long
    task inside a Jupyter cell.

    .. code-block: python
       with ui_events() as ui_poll:
          while some_condition:
             await ui_poll(10)  # Process upto 10 UI events if any happened
             do_some_more_compute()


    - Delay processing `execute_request` IPython kernel events
    - Calls `kernel.do_one_iteration()`
    - Schedule replay of any blocked `execute_request` events upon
      exiting from the context manager
    """
    shell = get_ipython()
    kernel = shell.kernel
    _backup_execute_request = kernel.shell_handlers["execute_request"]
    original_parent = (kernel._parent_ident, kernel.get_parent())

    events = []

    async def _execute_request(stream, ident, parent):
        # store away execute request for later and reset io back to the original cell
        events.append((stream, ident, parent))
        kernel.set_parent(*original_parent)

    async def poll(n=1):
        for _ in range(n):
            try:
                await kernel.do_one_iteration()
                # reset stdio back to original cell
                kernel.set_parent(*original_parent)
            except QueueEmpty:  # it's probably a bug in ipykernel, .do_one_iteration() should not throw
                return

    loop = asyncio.get_event_loop()
    assert loop.is_running()

    kernel.shell_handlers["execute_request"] = _execute_request
    try:
        yield poll
    finally:
        # Restore execute_request handler
        kernel.shell_handlers["execute_request"] = _backup_execute_request
        asyncio.ensure_future(_replay_events(kernel, events), loop=loop)


async def with_ui_events(its, n=1):
    """
    Deal with kernel ui events while processing a long sequence

    :param its: Iterator to pass through
    :param n:   Number of events to process in between items

    - Delay processing `execute_request` IPython kernel events
    - Inject calls to `kernel.do_one_iteration()` in between iterations
    - Schedule replay of any blocked `execute_request` events when data sequence is exhausted
    """
    with ui_events() as poll:
        try:
            for x in its:
                await poll(n)
                yield x
        except GeneratorExit:
            pass
        except Exception as e:
            raise e


async def run_ui_poll_loop(f, sleep=0.02, n=1):
    """
    Repeatedly call `f()` until it returns non-None value while also responding to widget events.

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

    async for x in with_ui_events(as_iterator(f, sleep), n):
        if x is not None:
            return x
