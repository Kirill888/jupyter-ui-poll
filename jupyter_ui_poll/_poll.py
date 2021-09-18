import asyncio
import sys
import time
from contextlib import contextmanager

import zmq
from IPython import get_ipython
from tornado.queues import QueueEmpty


class KernelWrapper:
    _current = None

    def __init__(self, shell, loop) -> None:
        kernel = shell.kernel

        self._shell = shell
        self._kernel = kernel
        self._loop = loop
        self._original_parent = (kernel._parent_ident, kernel.get_parent())
        self._events = []
        self._backup_execute_request = kernel.shell_handlers["execute_request"]

        shell.events.register("post_run_cell", self._post_run_cell_hook)
        kernel.shell_handlers["execute_request"] = self._execute_request_async

    def restore(self):
        if self._backup_execute_request is not None:
            self._kernel.shell_handlers["execute_request"] = self._backup_execute_request
            self._backup_execute_request = None

    def _reset_output(self):
        self._kernel.set_parent(*self._original_parent)

    def _execute_request(self, stream, ident, parent):
        # store away execute request for later and reset io back to the original cell
        self._events.append((stream, ident, parent))
        self._reset_output()

    async def _execute_request_async(self, stream, ident, parent):
        self._execute_request(stream, ident, parent)

    async def replay(self):
        kernel = self._kernel
        self.restore()

        sys.stdout.flush()
        sys.stderr.flush()
        for stream, ident, parent in self._events:
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

    async def do_one_iteration(self):
        try:
            await self._kernel.do_one_iteration()
            # reset stdio back to original cell
            self._reset_output()
        except QueueEmpty:  # it's probably a bug in ipykernel, .do_one_iteration() should not throw
            return

    def _post_run_cell_hook(self, _):
        self._shell.events.unregister("post_run_cell", self._post_run_cell_hook)
        self.restore()
        KernelWrapper._current = None
        asyncio.ensure_future(self.replay(), loop=self._loop)

    @staticmethod
    def get():
        if KernelWrapper._current is None:
            KernelWrapper._current = KernelWrapper(get_ipython(), asyncio.get_event_loop())
        return KernelWrapper._current


@contextmanager
def ui_events():
    """
    Gives you a async function you can call to process ui events while running a long
    task inside a Jupyter cell.

    .. code-block: python
       async with ui_events() as ui_poll:
          while some_condition:
             await ui_poll(10)  # Process upto 10 UI events if any happened
             do_some_more_compute()


    - Delay processing `execute_request` IPython kernel events
    - Calls `kernel.do_one_iteration()`
    - Schedule replay of any blocked `execute_request` events upon
      exiting from the context manager
    """
    kernel = KernelWrapper.get()

    async def poll(n=1):
        for _ in range(n):
            await kernel.do_one_iteration()

    yield poll


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
