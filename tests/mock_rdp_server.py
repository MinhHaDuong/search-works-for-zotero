"""A minimal Firefox RDP server for tests of bench/zotero_rdp_client.py.

Framing here is written independently of `bench/zotero_rdp_client.py`,
deliberately: if the client under test and this mock shared one framing
implementation, a bug in it could cancel out between sender and receiver and
never surface in a test that only talks to itself. This file re-implements
the same `[decimal length]:[utf-8 json]` format from the same source citation
the client's own docstring gives (`devtools/shared/transport/packets.js`),
independently, so a divergence between the two is exactly the framing bug a
test should catch.

Speaks just enough of the protocol path the client needs -- an initial
`root` hello, `getProcess`, `getTarget`, and `evaluateJSAsync` (an immediate
ack plus a later unsolicited `evaluationResult` event) -- with the actual
scenario supplied per-test as a `handle(sock)` callback, so this module owns
no scenario logic of its own.
"""

import json
import socket
import threading


def send_packet(sock: socket.socket, packet: dict) -> None:
    body = json.dumps(packet).encode("utf-8")
    sock.sendall(f"{len(body)}:".encode("ascii") + body)


def recv_packet(sock: socket.socket, buf: bytearray) -> tuple[dict | None, bytearray]:
    """Read exactly one packet, carrying leftover bytes in `buf` across calls.

    Returns `(None, buf)` on a clean close before a full packet arrived, so a
    handler that expects the peer to disconnect can tell that apart from a
    parse failure.
    """
    while b":" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            return None, buf
        buf += chunk
    header, _, rest = bytes(buf).partition(b":")
    length = int(header)
    buf = bytearray(rest)
    while len(buf) < length:
        chunk = sock.recv(4096)
        if not chunk:
            return None, buf
        buf += chunk
    packet_bytes, buf = bytes(buf[:length]), bytearray(buf[length:])
    return json.loads(packet_bytes.decode("utf-8")), buf


class MockRDPServer:
    """Accepts exactly one connection on an ephemeral localhost port and runs
    `handle(sock)` against it in a background thread."""

    def __init__(self, handle):
        self._handle = handle
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self.port = self._listener.getsockname()[1]
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            conn, _ = self._listener.accept()
        except OSError:
            return
        try:
            self._handle(conn)
        except OSError:
            # The scenario closed the connection on purpose (dropped-connection
            # tests) or the test process is tearing down; neither is this
            # server's failure to report.
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def close(self) -> None:
        self._listener.close()
        self._thread.join(timeout=5)
