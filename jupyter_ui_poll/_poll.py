import asyncio
import sys
import time
from inspect import iscoroutinefunction

import zmq
from IPython import get_ipython
from tornado.queues import QueueEmpty

from ._async_thread import AsyncThread


class KernelWrapper:
    _current = None

    def __init__(self, shell, loop) -> None:
        kernel = shell.kernel

        self._shell = shell
        self._kernel = kernel
        self._loop = loop
        self._original_parent = (
            kernel._parent_ident,
            kernel.get_parent()  # ipykernel 6+
            if hasattr(kernel, "get_parent")
            else kernel._parent_header,  # ipykernel < 6
        )
        self._events = []
        self._backup_execute_request = kernel.shell_handlers["execute_request"]
        self._aproc = None
        self._kernel_is_async = iscoroutinefunction(self._backup_execute_request)

        if self._kernel_is_async:  # ipykernel 6+
            kernel.shell_handlers["execute_request"] = self._execute_request_async
        else:
            # ipykernel < 6
            kernel.shell_handlers["execute_request"] = self._execute_request

        shell.events.register("post_run_cell", self._post_run_cell_hook)

    def restore(self):
        if self._backup_execute_request is not None:
            self._kernel.shell_handlers[
                "execute_request"
            ] = self._backup_execute_request
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
        shell_stream = getattr(
            kernel, "shell_stream", None
        )  # ipykernel 6 vs 5 differences

        for stream, ident, parent in self._events:
            kernel.set_parent(ident, parent)
            if kernel._aborting:
                kernel._send_abort_reply(stream, parent, ident)
            else:
                rr = kernel.execute_request(stream, ident, parent)
                if self._kernel_is_async:
                    await rr

                # replicate shell_dispatch behaviour
                sys.stdout.flush()
                sys.stderr.flush()
                if shell_stream is not None:  # 6+
                    kernel._publish_status("idle", "shell")
                    shell_stream.flush(zmq.POLLOUT)
                else:
                    kernel._publish_status("idle")

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

    async def _poll_async(self, n=1):
        for _ in range(n):
            await self.do_one_iteration()

    async def __aenter__(self):
        return self._poll_async

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def __enter__(self):
        if self._aproc is not None:
            raise ValueError("Nesting not supported")
        self._aproc = AsyncThread()
        return self._aproc.wrap(self._poll_async)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._aproc.terminate()
        self._aproc = None

    def wrap_iterator(self, its, n: int = 1):
        return IteratorWrapper(its, self, n=n)

    @staticmethod
    def get():
        if KernelWrapper._current is None:
            KernelWrapper._current = KernelWrapper(
                get_ipython(), asyncio.get_event_loop()
            )
        return KernelWrapper._current


class IteratorWrapper:
    def __init__(self, its, kernel: KernelWrapper, n: int = 1):
        self._its = its
        self._n = n
        self._kernel = kernel

    def __iter__(self):
        def _loop(kernel, its, n):
            with kernel as poll:
                try:
                    for x in its:
                        poll(n)
                        yield x
                except GeneratorExit:
                    pass
                except Exception as e:
                    raise e

        return _loop(self._kernel, self._its, self._n)

    def __aiter__(self):
        async def _loop(kernel, its, n):
            async with kernel as poll:
                for x in its:
                    await poll(n)
                    yield x

        return _loop(self._kernel, self._its, self._n)


def ui_events():
    """
    Gives you a function you can call to process ui events while running a long
    task inside a Jupyter cell.

    Support both async and sync operation.

    .. code-block: python
       async with ui_events() as ui_poll:
          while some_condition:
             await ui_poll(10)  # Process upto 10 UI events if any happened
             do_some_more_compute()

        with ui_events() as ui_poll:
          while some_condition:
             ui_poll(10)  # Process upto 10 UI events if any happened
             do_some_more_compute()

    - Delay processing `execute_request` IPython kernel events
    - Calls `kernel.do_one_iteration()`
    - Schedule replay of any blocked `execute_request` events upon
      exiting from the context manager
    """
    return KernelWrapper.get()


def with_ui_events(its, n=1):
    """
    Deal with kernel ui events while processing a long sequence

    :param its: Iterator to pass through
    :param n:   Number of events to process in between items

    - Delay processing `execute_request` IPython kernel events
    - Inject calls to `kernel.do_one_iteration()` in between iterations
    - Schedule replay of any blocked `execute_request` events when data sequence is exhausted
    """
    return KernelWrapper.get().wrap_iterator(its, n)


def run_ui_poll_loop(f, sleep=0.02, n=1):
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

    for x in with_ui_events(as_iterator(f, sleep), n):
        if x is not None:
            return x
