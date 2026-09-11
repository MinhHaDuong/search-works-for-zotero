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

There is no request-correlation id anywhere in this protocol: a reply is
matched to its request by the actor it came `from` and by arrival order,
nothing else. Two consequences shape `RDPConnection`, and they are why a
timeout here is fatal to the connection and not merely to the call:

- A same-actor packet carrying a `type` key is an EVENT, never a direct
  reply -- response templates do not set `type` (`Response.js`), event
  packets always do (`webconsole.js`). The console actor emits
  `consoleAPICall` for any `console.log` anywhere in the process, at any
  moment, including between a request and its own reply, so `from` alone
  does not identify a reply.
- After a timeout, an unknown number of replies for the ABANDONED request
  may still be in flight -- the server was never told the client stopped
  listening -- and none of them is distinguishable from the next request's
  reply. `RDPConnection` therefore poisons itself on any timeout: it closes
  the socket and raises `RDPConnectionClosed` on any later use. The cost is
  that a caller reusing one connection across an
  install/replace/disable/enable cycle must reconnect after a timeout; the
  alternative -- guessing how many stale packets to drain -- hands one
  call's result to another call silently, with no exception anywhere, which
  is how this was found (a call that evaluated `222` returned `111`).

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

A returned live `Promise` (e.g. from an async IIFE, since `evaluateJSAsync`
on this build rejects a bare top-level `await` with a SyntaxError -- it is
NOT auto-transformed the way Firefox's own Web Console front-end transforms
typed input before sending it) only comes back as its RESOLVED value if the
request itself asks for that: `evaluateJSAsync`'s `mapped` field, sent as
`{"await": true}`, makes `evaluateJS` unwrap a Promise-valued completion
before grip-ing it (`webconsole.js`, `prepareEvaluationResult`: `if
(mapped?.await && result?.class === "Promise") { awaitResult =
result.unsafeDereference(); }`, then `_maybeWaitForResponseResult` awaits
it). Without `mapped: {"await": true}` the same Promise comes back as an
object GRIP instead -- found the hard way, by first shipping without it and
getting `{"type": "object", "class": "Promise", ...}` back from a live
Zotero instead of the answer (ticket 0766's log). `eval_js` below always
sends `mapped: {"await": true}`, so an async IIFE resolves transparently.

The one gap this does NOT close: a REJECTED promise does not surface its
rejection reason here at all. `_maybeWaitForResponseResult`'s catch block
sets `topLevelAwaitRejected: true` and nothing else -- no message, no grip --
because Firefox's own console handles an unhandled rejection as a separate,
asynchronous "uncaught exception" resource, out of band from this response.
`eval_js` raises `RDPEvalError` on `topLevelAwaitRejected`, but with no
reason string to give you. Write eval code that catches its own errors and
returns a JSON string describing the outcome (`{"ok": false, "error":
String(e)}`) rather than letting a promise reject to the top level, if you
need to know why something failed.
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

    def __init__(self, transport: RDPTransport):
        self.transport = transport
        self._pending: list[dict] = []
        self._poisoned: str | None = None

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
        return cls(transport)

    def close(self) -> None:
        self.transport.close()

    def _check_usable(self) -> None:
        if self._poisoned is not None:
            raise RDPConnectionClosed(self._poisoned)

    def _poison(self, reason: str) -> None:
        """Give up on this connection for good and close the socket.

        Called on every timeout. Once a request is abandoned, an unknown
        number of replies for it may still be in flight -- the server does
        not know the client stopped listening -- and the protocol carries no
        request-correlation id, so nothing in a later packet distinguishes
        "the reply to the request you are waiting for" from "the reply to
        the one you gave up on". Draining a fixed number of stale packets
        would be a guess: a timed-out `eval_js` can leave behind an ack, an
        `evaluationResult`, both, or neither. Closing is the only answer that
        cannot silently misattribute one call's result to another; the cost
        is that a caller reusing one connection across an
        install/replace/disable/enable cycle must reconnect after a timeout.
        """
        self._poisoned = (
            f"connection abandoned after {reason}; replies to the abandoned "
            "request may still be in flight and the protocol has no "
            "request id to tell them from the next request's own -- "
            "reconnect rather than reuse this connection"
        )
        self.transport.close()

    def request(self, to: str, type_: str, timeout: float = 10.0, **fields) -> dict:
        """Send `{to, type, **fields}` and return actor `to`'s direct reply.

        A direct reply is recognised by TWO things, not one: it comes `from`
        the actor addressed AND it carries no `type` key. The second half
        matters because the same actor also emits unsolicited events at any
        moment -- a `console.log` anywhere in Zotero makes the console actor
        send `consoleAPICall` -- and those, per `Response.js` vs. the event
        packets in `webconsole.js`, are exactly the same-actor packets that
        DO carry `type`. Matching on `from` alone lets any such event answer
        whichever request happens to be in flight.

        Any packet read meanwhile that is not that direct reply is queued
        for `wait_for_event` rather than discarded -- it may be the very
        event a subsequent call is waiting for.

        Raises `RDPConnectionClosed` immediately if an earlier call on this
        connection timed out (see `_poison`).
        """
        self._check_usable()
        packet = {"to": to, "type": type_}
        packet.update(fields)
        self.transport.send(packet)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._poison(f"{type_!r} to {to!r} went unanswered for {timeout}s")
                raise RDPTimeout(
                    f"no response from {to!r} to {type_!r} within {timeout}s"
                )
            try:
                reply = self.transport.recv(timeout=remaining)
            except RDPTimeout:
                self._poison(f"{type_!r} to {to!r} went unanswered for {timeout}s")
                raise
            if reply.get("from") != to or "type" in reply:
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
        it. Raises `RDPConnectionClosed` immediately if an earlier call on
        this connection timed out (see `_poison`).
        """
        self._check_usable()

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
                self._poison(
                    f"no {event_type!r} from {actor!r} within {timeout}s"
                )
                raise RDPTimeout(
                    f"no {event_type!r} from {actor!r} within {timeout}s"
                )
            try:
                packet = self.transport.recv(timeout=remaining)
            except RDPTimeout:
                self._poison(
                    f"no {event_type!r} from {actor!r} within {timeout}s"
                )
                raise
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

        Sends `mapped: {"await": true}` on every call, so a `Promise` your
        code returns (an async IIFE, or a bare async function call) is
        awaited and unwrapped server-side before being sent back -- see this
        module's own docstring for why that field is needed at all and what
        it does NOT cover (a rejected promise's reason is not recoverable
        here; catch your own errors in the eval code).

        Prefer eval code that returns a JSON-primitive (a string, a number,
        a boolean) or a string you built yourself with `JSON.stringify(...)`
        inside the eval. A returned live object still comes back as an RDP
        "grip" -- an object DESCRIPTOR, not the object's own fields --
        because that is what the protocol sends for anything that is not a
        primitive; `JSON.stringify` inside the evaluated code sidesteps
        that.

        Raises `RDPEvalError` if the JavaScript itself raised (using the
        `hasException` flag the actor sets, per `webconsole.js`'s own
        `evaluateJS`: `hasException: errorGrip !== null`) or if an awaited
        promise rejected (`topLevelAwaitRejected`, with no reason attached
        -- see this module's docstring).
        """
        if self.console_actor is None:
            self.attach_chrome_target(timeout=timeout)
        ack = self.conn.request(
            self.console_actor,
            "evaluateJSAsync",
            timeout=timeout,
            text=code,
            mapped={"await": True},
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
        if event.get("topLevelAwaitRejected"):
            raise RDPEvalError(
                "an awaited promise rejected; Firefox's console reports the "
                "reason out of band (a separate uncaught-exception resource "
                "this client does not subscribe to) rather than in this "
                "response -- write eval code that catches its own errors and "
                "returns a description of the failure if you need to know "
                "why",
                event,
            )
        return event.get("result")


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=6000)
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="seconds to wait for each reply and for the evaluation result. "
        "A timeout is terminal for the connection, not just for the call: "
        "the socket is closed and a reconnect is required, because replies "
        "to the abandoned request may still be in flight and this protocol "
        "has no request id to tell them apart from the next request's own.",
    )
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
