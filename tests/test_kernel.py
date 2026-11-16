"""
Run ``run_ui_poll_loop`` inside a real kernel and drive it the way a frontend does.

The test talks to the kernel with jupyter_client, so it exercises whichever ipykernel
is installed. CI runs it against several ipykernel versions.
"""

import queue
import time

import pytest

pytest.importorskip("jupyter_client")
pytest.importorskip("ipykernel")
pytest.importorskip("ipywidgets")

from jupyter_client.manager import start_new_kernel  # noqa: E402

SETUP = """
import ipywidgets as w
from traitlets import Unicode

class Probe(w.DOMWidget):
    synced = Unicode("").tag(sync=True)
    custom = Unicode("")

    def __init__(self):
        super().__init__()
        self.on_msg(lambda _w, content, _b: setattr(self, "custom", content["value"]))

probe = Probe()
print(probe.comm.comm_id)
"""

POLL = """
import time
from jupyter_ui_poll import run_ui_poll_loop

start = time.monotonic()
result = run_ui_poll_loop(
    lambda: probe.{attr} or ("TIMEOUT" if time.monotonic() - start > 10 else None),
    sleep=0.05,
)
print(result)
"""

ASYNC_POLL = """
import time
from jupyter_ui_poll import ui_events

start = time.monotonic()
async with ui_events() as poll:
    while not probe.custom and time.monotonic() - start < 10:
        await poll(10)
        time.sleep(0.05)
print(probe.custom or "TIMEOUT")
"""

UPDATE = {"method": "update", "state": {"synced": "from-update"}, "buffer_paths": []}
CUSTOM = {"method": "custom", "content": {"value": "from-custom"}}


@pytest.fixture
def kernel():
    km, kc = start_new_kernel(kernel_name="python3")
    try:
        yield kc
    finally:
        kc.stop_channels()
        km.shutdown_kernel(now=True)


def _wait(kc, msg_ids, timeout=30):
    """Collect stdout of each request and the order in which they finished."""
    output = {msg_id: "" for msg_id in msg_ids}
    finished = []
    deadline = time.monotonic() + timeout
    while len(finished) < len(msg_ids) and time.monotonic() < deadline:
        try:
            msg = kc.get_iopub_msg(timeout=1)
        except queue.Empty:
            continue
        parent = msg["parent_header"].get("msg_id")
        if parent not in output:
            continue
        if msg["msg_type"] == "stream":
            output[parent] += msg["content"]["text"]
        elif msg["msg_type"] == "error":
            output[parent] += "ERROR " + msg["content"]["evalue"]
        elif (
            msg["msg_type"] == "status" and msg["content"]["execution_state"] == "idle"
        ):
            if parent not in finished:
                finished.append(parent)
    return {k: v.strip() for k, v in output.items()}, finished


def _shell_replies(kc, msg_ids, timeout=10):
    """Return the reply type received on the shell channel for each request."""
    replies = {}
    deadline = time.monotonic() + timeout
    while len(replies) < len(msg_ids) and time.monotonic() < deadline:
        try:
            msg = kc.get_shell_msg(timeout=0.5)
        except queue.Empty:
            continue
        parent = msg["parent_header"].get("msg_id")
        if parent in msg_ids:
            replies[parent] = msg["msg_type"]
    return [replies.get(msg_id) for msg_id in msg_ids]


def _send_comm_msg(kc, comm_id, data):
    msg = kc.session.msg("comm_msg", {"comm_id": comm_id, "data": data})
    kc.session.send(kc.shell_channel.socket, msg)


def _setup(kc):
    msg_id = kc.execute(SETUP)
    output, _ = _wait(kc, [msg_id])
    return output[msg_id].split()[-1]


@pytest.mark.parametrize(
    ("attr", "data", "expected"),
    [("synced", UPDATE, "from-update"), ("custom", CUSTOM, "from-custom")],
)
def test_poll_loop_processes_comm_messages(kernel, attr, data, expected):
    comm_id = _setup(kernel)

    poll_id = kernel.execute(POLL.format(attr=attr))
    time.sleep(1)  # the poll loop is now blocking the cell
    # A cell queued while polling (e.g. "Run All") must run only after the poll returns.
    next_id = kernel.execute(f"print('next', probe.{attr})")
    time.sleep(0.5)
    _send_comm_msg(kernel, comm_id, data)

    output, finished = _wait(kernel, [poll_id, next_id])

    assert output[poll_id] == expected
    assert output[next_id] == f"next {expected}"
    assert finished == [poll_id, next_id]
    # the frontend only marks a cell as done when it gets its execute_reply
    assert _shell_replies(kernel, [poll_id, next_id]) == ["execute_reply"] * 2


def test_async_ui_events_processes_comm_messages(kernel):
    comm_id = _setup(kernel)

    poll_id = kernel.execute(ASYNC_POLL)
    time.sleep(1)
    next_id = kernel.execute("print('next', probe.custom)")
    time.sleep(0.5)
    _send_comm_msg(kernel, comm_id, CUSTOM)

    output, finished = _wait(kernel, [poll_id, next_id])

    assert output[poll_id] == "from-custom"
    assert output[next_id] == "next from-custom"
    assert finished == [poll_id, next_id]


def test_kernel_works_normally_after_polling(kernel):
    comm_id = _setup(kernel)

    for value in ("first", "second"):
        reset_id = kernel.execute("probe.custom = ''")
        _wait(kernel, [reset_id])
        poll_id = kernel.execute(POLL.format(attr="custom"))
        time.sleep(1)
        _send_comm_msg(
            kernel, comm_id, {"method": "custom", "content": {"value": value}}
        )
        output, _ = _wait(kernel, [poll_id])
        assert output[poll_id] == value

    # comm messages received while idle are still handled as usual
    _send_comm_msg(kernel, comm_id, {"method": "custom", "content": {"value": "idle"}})
    time.sleep(0.5)
    check_id = kernel.execute("print(probe.custom)")
    output, _ = _wait(kernel, [check_id])
    assert output[check_id] == "idle"


def _ipykernel_version():
    from importlib.metadata import version

    return tuple(int(part) for part in version("ipykernel").split(".")[:2])


@pytest.mark.skipif(
    (7, 0) <= _ipykernel_version() < (7, 4),
    reason="ipykernel 7.0-7.3 can strand shell requests under load (ipython/ipykernel#1529)",
)
@pytest.mark.parametrize(
    "poll_code", [POLL.format(attr="custom"), ASYNC_POLL], ids=["sync", "async"]
)
def test_shell_channel_keeps_working_after_busy_polling(kernel, poll_code):
    # A frontend sends other shell requests while a cell is blocked (kernel_info,
    # comm_info, ...). Reading them behind the kernel's back must not leave its shell
    # channel deaf once polling is over.
    comm_id = _setup(kernel)

    poll_id = kernel.execute(poll_code)
    time.sleep(0.5)
    for _ in range(30):
        kernel.kernel_info()
        kernel.comm_info()
        time.sleep(0.01)
    _send_comm_msg(kernel, comm_id, CUSTOM)
    for _ in range(30):
        kernel.kernel_info()
        kernel.comm_info()
    _wait(kernel, [poll_id])
    time.sleep(0.5)

    info_id = kernel.kernel_info()
    next_id = kernel.execute("print('alive')")
    output, _ = _wait(kernel, [next_id])

    assert output[next_id] == "alive"
    assert _shell_replies(kernel, [info_id, next_id]) == [
        "kernel_info_reply",
        "execute_reply",
    ]
