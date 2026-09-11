#!/usr/bin/env python3
"""A client for Firefox's Remote Debugging Protocol (RDP), scoped to one job:
attach to a running Zotero's chrome/parent-process target and eval privileged
JavaScript in it, from outside the Zotero process, with no plugin and no GUI
automation. Ticket 0766, in service of 0727 (the sitter's disappearance),
whose next experiment needs a scripted install/replace/disable/enable cycle
and cannot get one through a human clicking Tools -> Add-ons each time.

This is deliberately NOT a general DevTools client. It knows three requests
(`getProcess`, `getTarget`, `evaluateJSAsync`) and nothing about tabs,
breakpoints, or any other actor. Every wire detail below was re-derived from
Zotero 10.0.2's own shipped source (`/opt/zotero7/omni.ja` and
`/opt/zotero7/app/omni.ja`, extracted with `unzip`) rather than assumed —
0766's ticket body cites the exact files and line ranges; the short version:

- Packet framing is `[decimal length]:[utf-8 json]`, nothing else
  (`devtools/shared/transport/packets.js`).
- A spec's `request`/`response` template keys become wire field names
  verbatim (`devtools/shared/protocol/{Request,Response}.js`), so
  `getProcess(id=0)` is `{to: "root", type: "getProcess", id: 0}` and its
  reply is `{from: "root", processDescriptor: {...}}` — not, for instance,
  `{value: {...}}` or a bare positional array.
- `evaluateJSAsync` replies IMMEDIATELY with just `{resultID}` — an
  acknowledgement that the request was accepted, not the answer — and
  delivers the real result later as an UNSOLICITED event packet
  `{from: consoleActor, type: "evaluationResult", resultID, result, ...,
  hasException, exceptionMessage}` (`devtools/server/actors/webconsole.js`,
  `evaluateJSAsync` and `evaluateJS`). A client that returns the ack is
  wrong in a way that looks right until the caller reads `resultID` as an
  answer.

Nothing here calls `AddonsActor.installTemporaryAddon` or any add-on
install/uninstall method. That actor's only two methods
(`installTemporaryAddon`, `uninstallAddon`,
`devtools/server/actors/addon/addons.js`) are the WRONG path for 0727's
purpose — `installTemporaryAddon` is Firefox's non-persistent "Load Temporary
Add-on" mechanism and does not exercise the `extensions.json` machinery a
real install does. The real, persistent install path
(`AddonManager.getInstallForFile` + `installAddonFromAOMWithOptions`, see
`chrome/toolkit/content/mozapps/extensions/aboutaddonsCommon.js`,
`installAddonsFromFilePicker`) is reachable only via a plain chrome eval —
which is exactly what this client provides and does not itself invoke. That
line is 0766's, not this module's: this module is safe to use for anything
because it makes no install decision at all, it only opens the door.

Before a client can attach, the target Zotero process needs a real RDP
listener running with `DevToolsServer.allowChromeProcess = true`. See
`bench/zotero_arm_devtools_server.js` for how to open one in an
already-running Zotero with no restart (Tools -> Developer -> Run
JavaScript), and `--start-debugger-server <port>` for the CLI-flag,
restart-required alternative documented in `zotero -h`. EITHER path also
needs `devtools.debugger.prompt-connection` set to `false` (also handled by
`zotero_arm_devtools_server.js`), or every connection hangs forever waiting
on a UI prompt nothing will ever answer -- this was found by running this
client against a live Zotero, not by reading the startup flag's own code,
which does not mention it (`devtools/shared/security/{auth,socket}.js`).

A returned live `Promise` (e.g. from wrapping `await`-ing code in an async
IIFE, since `evaluateJSAsync` on this build does not evaluate bare top-level
`await`) does NOT come back as its resolved value -- only a promise the
console's OWN top-level-await handling produces gets unwrapped
(`webconsole.js`, `_maybeWaitForResponseResult`, gated on
`response.awaitResult`). An IIFE's promise comes back as an object GRIP
whose `preview.ownProperties["<value>"].value` holds the resolved value if
you had it `JSON.stringify` itself before returning -- ugly, but observed
working end to end against a live Zotero (ticket 0766's log). Prefer eval
code that resolves synchronously; when it cannot, expect and unwrap the grip
preview rather than treating a `class: "Promise"` result as a client bug.
"""

import argparse
import json
import socket
import sys
import time


class RDPError(Exception):
    """The protocol was violated, or the remote actor reported an error."""


class RDPTimeout(RDPError):
    """No matching packet arrived within the caller's deadline."""


class RDPConnectionClosed(RDPError):
    """The socket closed (locally observed as a short read or a send failure)
    before the expected packet arrived. Distinguished from RDPTimeout because
    a caller that retries a dropped connection needs to reconnect, not wait
    longer."""


class RDPEvalError(RDPError):
    """The evaluated JavaScript itself raised. Carries the raw `evaluationResult`
    event so a caller that wants the exception grip, not just the message,
    does not have to re-parse anything."""

    def __init__(self, message: str, event: dict):
        super().__init__(message)
        self.event = event


#: Header exceeding this many bytes before a colon is found is not a length
#: prefix -- it is a malformed stream. 20 matches this repo's own reading of
#: the packet format's own historical bound (packets.js's PACKET_LENGTH_MAX
#: comment); this client does not need to send packets anywhere near that
#: large, so a header this long can only mean framing has been lost.
_MAX_HEADER_BYTES = 20

#: id=0 is the parent (chrome) process, by root.js's own convention: "The
#: parent process has id == 0, based on ProcessActorList::getList
#: implementation" (server/actors/root.js, inside getProcess()).
PARENT_PROCESS_ID = 0


class RDPTransport:
    """Packet framing over a raw TCP socket. Nothing here knows what an actor
    is; it reads and writes whole JSON packets and nothing else."""

    def __init__(self, sock: socket.socket):
        self._sock = sock
        self._buf = b""

    @classmethod
    def connect(cls, host: str, port: int, timeout: float = 10.0) -> "RDPTransport":
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as exc:
            raise RDPConnectionClosed(
                f"could not connect to {host}:{port}: {exc}"
            ) from exc
        return cls(sock)

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    def send(self, packet: dict) -> None:
        body = json.dumps(packet).encode("utf-8")
        header = f"{len(body)}:".encode("ascii")
        try:
            self._sock.sendall(header + body)
        except OSError as exc:
            raise RDPConnectionClosed(f"send failed: {exc}") from exc

    def recv(self, timeout: float | None = None) -> dict:
        """Block for exactly one framed packet and return its decoded JSON.

        `timeout` is a budget for the WHOLE packet, not a per-syscall value:
        a slow trickle of one byte at a time must not get `timeout` seconds
        per byte. Buffers across calls, so a second packet that arrived
        packed into the same TCP segment as the first is not dropped.
        """
        deadline = None if timeout is None else time.monotonic() + timeout

        def remaining() -> float | None:
            if deadline is None:
                return None
            left = deadline - time.monotonic()
            if left <= 0:
                raise RDPTimeout(f"no packet within {timeout}s")
            return left

        while b":" not in self._buf:
            if len(self._buf) > _MAX_HEADER_BYTES:
                raise RDPError(
                    f"packet header exceeded {_MAX_HEADER_BYTES} bytes "
                    f"with no ':' found: {self._buf!r}"
                )
            self._sock.settimeout(remaining())
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout as exc:
                raise RDPTimeout(f"no packet within {timeout}s") from exc
            except OSError as exc:
                raise RDPConnectionClosed(f"recv failed: {exc}") from exc
            if not chunk:
                raise RDPConnectionClosed(
                    "connection closed while reading a packet header"
                )
            self._buf += chunk

        header, _, rest = self._buf.partition(b":")
        try:
            length = int(header)
        except ValueError as exc:
            raise RDPError(f"malformed packet length {header!r}") from exc
        if length < 0:
            raise RDPError(f"negative packet length {length}")
        self._buf = rest

        while len(self._buf) < length:
            self._sock.settimeout(remaining())
            try:
                chunk = self._sock.recv(max(4096, length - len(self._buf)))
            except socket.timeout as exc:
                raise RDPTimeout(f"no packet within {timeout}s") from exc
            except OSError as exc:
                raise RDPConnectionClosed(f"recv failed: {exc}") from exc
            if not chunk:
                raise RDPConnectionClosed("connection closed mid-packet")
            self._buf += chunk

        packet_bytes, self._buf = self._buf[:length], self._buf[length:]
        try:
            decoded = json.loads(packet_bytes.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RDPError(f"packet body is not valid JSON: {exc}") from exc
        if not isinstance(decoded, dict):
            raise RDPError(f"packet body is not a JSON object: {decoded!r}")
        return decoded


class RDPConnection:
    """One RDP session: request/response against a named actor, plus a queue
    for the unsolicited event packets a request's own response can be
    interleaved with (the server is free to deliver another actor's event
    between a request and its reply)."""

    def __init__(self, transport: RDPTransport, hello: dict):
        self.transport = transport
        self.hello = hello
        self._pending: list[dict] = []

    @classmethod
    def connect(
        cls, host: str = "localhost", port: int = 6000, timeout: float = 10.0
    ) -> "RDPConnection":
        transport = RDPTransport.connect(host, port, timeout=timeout)
        try:
            hello = transport.recv(timeout=timeout)
        except RDPError:
            transport.close()
            raise
        if hello.get("from") != "root":
            transport.close()
            raise RDPError(
                f"greeting packet did not come from the root actor: {hello!r}"
            )
        return cls(transport, hello)

    def close(self) -> None:
        self.transport.close()

    def request(self, to: str, type_: str, timeout: float = 10.0, **fields) -> dict:
        """Send `{to, type, **fields}` and return actor `to`'s direct reply.

        Any packet read meanwhile that is not that direct reply is queued
        for `wait_for_event` rather than discarded -- it may be the very
        event a subsequent call is waiting for.
        """
        packet = {"to": to, "type": type_}
        packet.update(fields)
        self.transport.send(packet)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RDPTimeout(
                    f"no response from {to!r} to {type_!r} within {timeout}s"
                )
            reply = self.transport.recv(timeout=remaining)
            if reply.get("from") != to:
                self._pending.append(reply)
                continue
            if "error" in reply:
                raise RDPError(
                    f"{to} rejected {type_!r}: {reply.get('error')}: "
                    f"{reply.get('message')}"
                )
            return reply

    def wait_for_event(
        self, actor: str, event_type: str, match=None, timeout: float = 10.0
    ) -> dict:
        """Wait for an unsolicited `{from: actor, type: event_type, ...}`.

        Checks packets already queued by `request` first, since a fast
        server can deliver the event before the caller starts waiting for
        it.
        """

        def matches(packet: dict) -> bool:
            return (
                packet.get("from") == actor
                and packet.get("type") == event_type
                and (match is None or match(packet))
            )

        for i, packet in enumerate(self._pending):
            if matches(packet):
                return self._pending.pop(i)

        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RDPTimeout(
                    f"no {event_type!r} from {actor!r} within {timeout}s"
                )
            packet = self.transport.recv(timeout=remaining)
            if matches(packet):
                return packet
            self._pending.append(packet)


class ZoteroRDPClient:
    """Attach to a live Zotero's chrome/parent-process target and eval."""

    def __init__(self, conn: RDPConnection):
        self.conn = conn
        self.console_actor: str | None = None

    @classmethod
    def connect(
        cls, host: str = "localhost", port: int = 6000, timeout: float = 10.0
    ) -> "ZoteroRDPClient":
        return cls(RDPConnection.connect(host, port, timeout=timeout))

    def close(self) -> None:
        self.conn.close()

    def attach_chrome_target(self, timeout: float = 10.0) -> str:
        """root -> getProcess(id=0) -> getTarget -> consoleActor.

        Requires the server's `allowChromeProcess` to be true (set by
        `bench/zotero_arm_devtools_server.js` or by the
        `--start-debugger-server` startup path); `root.js`'s `getProcess`
        throws `{error: "forbidden", ...}` otherwise, which surfaces here as
        an `RDPError` naming that reason.
        """
        reply = self.conn.request(
            "root", "getProcess", timeout=timeout, id=PARENT_PROCESS_ID
        )
        descriptor = reply.get("processDescriptor")
        if not isinstance(descriptor, dict) or "actor" not in descriptor:
            raise RDPError(
                f"getProcess reply had no processDescriptor.actor: {reply!r}"
            )
        descriptor_actor = descriptor["actor"]

        target_reply = self.conn.request(
            descriptor_actor, "getTarget", timeout=timeout
        )
        process_form = target_reply.get("process")
        if not isinstance(process_form, dict) or "consoleActor" not in process_form:
            raise RDPError(
                f"getTarget reply had no process.consoleActor: {target_reply!r}"
            )
        self.console_actor = process_form["consoleActor"]
        return self.console_actor

    def eval_js(self, code: str, timeout: float = 10.0):
        """Evaluate `code` with chrome privilege; return its result.

        Prefer eval code that returns a JSON-primitive (a string, a number,
        a boolean) or a string you built yourself with `JSON.stringify(...)`
        inside the eval. A returned live object comes back as an RDP "grip"
        -- an object DESCRIPTOR, not the object's own fields -- because that
        is what the protocol sends for anything that is not a primitive;
        `JSON.stringify` inside the evaluated code sidesteps that.

        Raises `RDPEvalError` if the JavaScript itself raised, using the
        `hasException` flag the actor sets rather than checking a nullable
        field, per `webconsole.js`'s own `evaluateJS`:
        `hasException: errorGrip !== null`.
        """
        if self.console_actor is None:
            self.attach_chrome_target(timeout=timeout)
        ack = self.conn.request(
            self.console_actor, "evaluateJSAsync", timeout=timeout, text=code
        )
        result_id = ack.get("resultID")
        if not result_id:
            raise RDPError(f"evaluateJSAsync ack had no resultID: {ack!r}")
        event = self.conn.wait_for_event(
            self.console_actor,
            "evaluationResult",
            match=lambda p: p.get("resultID") == result_id,
            timeout=timeout,
        )
        if event.get("hasException"):
            message = event.get("exceptionMessage") or event.get("exception")
            raise RDPEvalError(f"eval raised: {message}", event)
        return event.get("result")


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6000)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "code",
        help="JavaScript to eval in the attached chrome target "
        "(wrap it in JSON.stringify(...) to get a readable value back)",
    )
    args = parser.parse_args(argv)

    client = ZoteroRDPClient.connect(args.host, args.port, timeout=args.timeout)
    try:
        result = client.eval_js(args.code, timeout=args.timeout)
    except RDPEvalError as exc:
        print(f"eval raised: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
