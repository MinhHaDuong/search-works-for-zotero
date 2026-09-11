"""`bench/zotero_rdp_client.py` -- against a local mock, never a real Zotero.

Ticket 0766. The client's job is to attach to a real Zotero's chrome/parent-
process target over Firefox's Remote Debugging Protocol and eval, so that
0727's next experiment (many install/replace/disable/enable cycles run
unattended) does not need a human clicking a file picker each time. Its own
correctness -- packet framing, the getProcess/getTarget/eval attach sequence,
error and timeout handling -- must not depend on a live Zotero being present,
so every test here talks only to `tests/mock_rdp_server.py`, a from-scratch
re-implementation of the wire format (not a reuse of this module's own
framing code -- see that file's docstring for why sharing one implementation
between the two sides would hide exactly the class of bug a test should
catch).

`test_eval_returns_result_not_ack` is this suite's red step: `evaluateJSAsync`
replies immediately with just `{resultID}`, an acknowledgement, and the real
answer arrives later as an unsolicited `evaluationResult` event
(`devtools/server/actors/webconsole.js`, cited in full in
`bench/zotero_rdp_client.py`'s own docstring and in ticket 0766). A client
that returns the ack instead of waiting for the event passes every test that
only checks "did eval_js return without raising" and fails only this one.
"""

import socket
import sys
import threading
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "bench") not in sys.path:
    sys.path.insert(0, str(REPO / "bench"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from zotero_rdp_client import (  # noqa: E402
    RDPConnectionClosed,
    RDPError,
    RDPEvalError,
    RDPTimeout,
    RDPTransport,
    ZoteroRDPClient,
)

from mock_rdp_server import MockRDPServer, recv_packet, send_packet  # noqa: E402


# --- packet framing, with no server at all ---------------------------------

@pytest.mark.integration
def test_framing_round_trips_through_a_real_socket():
    """send() writes `[len]:[json]`; recv() parses exactly that back, even
    when the two calls happen to write in one chunk. `socket.socketpair()`
    gives two connected local sockets with no listener/thread needed."""
    left, right = socket.socketpair()
    try:
        sender = RDPTransport(left)
        receiver = RDPTransport(right)
        sender.send({"from": "root", "hello": True})
        sender.send({"from": "root", "n": 2})
        assert receiver.recv(timeout=5) == {"from": "root", "hello": True}
        assert receiver.recv(timeout=5) == {"from": "root", "n": 2}
    finally:
        left.close()
        right.close()


@pytest.mark.integration
def test_framing_handles_a_packet_delivered_one_byte_at_a_time():
    """The length prefix and body may arrive over many small reads. A
    parser that assumes one recv() call returns one packet is wrong in a way
    that a real, unbuffered TCP stream will eventually expose."""
    left, right = socket.socketpair()
    try:
        receiver = RDPTransport(right)
        raw = b'11:{"n": true}'
        for i in range(len(raw)):
            left.sendall(raw[i:i + 1])
        assert receiver.recv(timeout=5) == {"n": True}
    finally:
        left.close()
        right.close()


def test_framing_rejects_a_header_with_no_colon():
    left, right = socket.socketpair()
    try:
        receiver = RDPTransport(right)
        left.sendall(b"x" * 25)
        left.close()
        with pytest.raises(RDPError):
            receiver.recv(timeout=5)
    finally:
        left.close()
        right.close()


# --- scenarios against the mock server --------------------------------------

def _hello(sock, **fields):
    send_packet(sock, {"from": "root", "applicationType": "zotero", **fields})


def _happy_path_handle(sock):
    _hello(sock)
    buf = bytearray()

    packet, buf = recv_packet(sock, buf)
    assert packet["to"] == "root" and packet["type"] == "getProcess" and packet["id"] == 0
    send_packet(sock, {"from": "root", "processDescriptor": {"actor": "process0"}})

    packet, buf = recv_packet(sock, buf)
    assert packet["to"] == "process0" and packet["type"] == "getTarget"
    send_packet(sock, {
        "from": "process0",
        "process": {"actor": "target0", "consoleActor": "console0"},
    })

    packet, buf = recv_packet(sock, buf)
    assert packet["to"] == "console0" and packet["type"] == "evaluateJSAsync"
    assert packet["text"] == "1+1"
    # Without `mapped: {"await": true}`, a Promise-valued eval (e.g. an async
    # IIFE) comes back as an unresolved object grip instead of its value --
    # found by running against a live Zotero, see this client's docstring.
    assert packet["mapped"] == {"await": True}
    send_packet(sock, {"from": "console0", "resultID": "1-0"})
    send_packet(sock, {
        "from": "console0", "type": "evaluationResult", "resultID": "1-0",
        "hasException": False, "result": 2,
    })


def test_attach_and_eval_happy_path():
    server = MockRDPServer(_happy_path_handle)
    try:
        client = ZoteroRDPClient.connect("127.0.0.1", server.port, timeout=5)
        try:
            assert client.eval_js("1+1", timeout=5) == 2
        finally:
            client.close()
    finally:
        server.close()


def test_eval_returns_result_not_ack():
    """The red-step test named in this file's docstring: `eval_js` must
    return the `evaluationResult` event's `result` (2), not the immediate
    `{resultID: "1-0"}` acknowledgement `evaluateJSAsync` replies with
    first."""
    server = MockRDPServer(_happy_path_handle)
    try:
        client = ZoteroRDPClient.connect("127.0.0.1", server.port, timeout=5)
        try:
            result = client.eval_js("1+1", timeout=5)
            assert result != {"resultID": "1-0"}
            assert result == 2
        finally:
            client.close()
    finally:
        server.close()


def _exception_handle(sock):
    _hello(sock)
    buf = bytearray()
    packet, buf = recv_packet(sock, buf)
    send_packet(sock, {"from": "root", "processDescriptor": {"actor": "process0"}})
    packet, buf = recv_packet(sock, buf)
    send_packet(sock, {
        "from": "process0",
        "process": {"actor": "target0", "consoleActor": "console0"},
    })
    packet, buf = recv_packet(sock, buf)
    send_packet(sock, {"from": "console0", "resultID": "1-0"})
    send_packet(sock, {
        "from": "console0", "type": "evaluationResult", "resultID": "1-0",
        "hasException": True, "exceptionMessage": "boom",
    })


def test_eval_raises_on_a_javascript_exception():
    server = MockRDPServer(_exception_handle)
    try:
        client = ZoteroRDPClient.connect("127.0.0.1", server.port, timeout=5)
        try:
            with pytest.raises(RDPEvalError, match="boom"):
                client.eval_js("throw new Error('boom')", timeout=5)
        finally:
            client.close()
    finally:
        server.close()


def _rejected_await_handle(sock):
    """`_maybeWaitForResponseResult`'s own catch block sets only
    `topLevelAwaitRejected: true` on a rejected awaited promise -- no
    `hasException`, no message, no grip (`webconsole.js`). A client that
    checks `hasException` alone treats this as a silent `None` success."""
    _hello(sock)
    buf = bytearray()
    packet, buf = recv_packet(sock, buf)
    send_packet(sock, {"from": "root", "processDescriptor": {"actor": "process0"}})
    packet, buf = recv_packet(sock, buf)
    send_packet(sock, {
        "from": "process0",
        "process": {"actor": "target0", "consoleActor": "console0"},
    })
    packet, buf = recv_packet(sock, buf)
    send_packet(sock, {"from": "console0", "resultID": "1-0"})
    send_packet(sock, {
        "from": "console0", "type": "evaluationResult", "resultID": "1-0",
        "hasException": False, "topLevelAwaitRejected": True,
    })


def test_eval_raises_rather_than_returning_none_on_a_rejected_promise():
    server = MockRDPServer(_rejected_await_handle)
    try:
        client = ZoteroRDPClient.connect("127.0.0.1", server.port, timeout=5)
        try:
            with pytest.raises(RDPEvalError):
                client.eval_js(
                    "(async function(){ throw new Error('x'); })()", timeout=5
                )
        finally:
            client.close()
    finally:
        server.close()


def _forbidden_handle(sock):
    """`allowChromeProcess` is false: root.js's own getProcess() throws
    `{error: "forbidden", ...}` rather than handing out a descriptor."""
    _hello(sock)
    buf = bytearray()
    packet, buf = recv_packet(sock, buf)
    send_packet(sock, {
        "from": "root", "error": "forbidden",
        "message": "You are not allowed to debug chrome.",
    })


def test_attach_surfaces_the_forbidden_error_by_name():
    server = MockRDPServer(_forbidden_handle)
    try:
        client = ZoteroRDPClient.connect("127.0.0.1", server.port, timeout=5)
        try:
            with pytest.raises(RDPError, match="forbidden"):
                client.attach_chrome_target(timeout=5)
        finally:
            client.close()
    finally:
        server.close()


def _drop_after_getprocess_handle(sock):
    _hello(sock)
    buf = bytearray()
    recv_packet(sock, buf)
    sock.close()


@pytest.mark.integration
def test_dropped_connection_raises_connection_closed_not_timeout():
    """A closed socket and a slow server are different failures for a caller
    deciding whether to reconnect or wait longer -- distinguished here by
    exception type, not just by message text."""
    server = MockRDPServer(_drop_after_getprocess_handle)
    try:
        client = ZoteroRDPClient.connect("127.0.0.1", server.port, timeout=5)
        try:
            with pytest.raises(RDPConnectionClosed):
                client.attach_chrome_target(timeout=5)
        finally:
            client.close()
    finally:
        server.close()


def _never_respond_handle(sock, stop_event):
    _hello(sock)
    buf = bytearray()
    recv_packet(sock, buf)
    stop_event.wait(10)


@pytest.mark.integration
def test_request_times_out_rather_than_blocking_forever():
    stop_event = threading.Event()
    server = MockRDPServer(lambda sock: _never_respond_handle(sock, stop_event))
    try:
        client = ZoteroRDPClient.connect("127.0.0.1", server.port, timeout=5)
        try:
            started = time.monotonic()
            with pytest.raises(RDPTimeout):
                client.attach_chrome_target(timeout=0.3)
            assert time.monotonic() - started < 5, "timeout did not bound the wait"
        finally:
            client.close()
    finally:
        stop_event.set()
        server.close()


def _wrong_hello_handle(sock):
    send_packet(sock, {"from": "not-root", "surprising": True})


def test_connect_rejects_a_hello_not_from_root():
    server = MockRDPServer(_wrong_hello_handle)
    try:
        with pytest.raises(RDPError):
            ZoteroRDPClient.connect("127.0.0.1", server.port, timeout=5)
    finally:
        server.close()
