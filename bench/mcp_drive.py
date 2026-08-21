#!/usr/bin/env python3
"""Minimal stdio JSON-RPC driver for an MCP server, for probing Zoteus."""
import argparse
import json
import logging
import os
import subprocess
import sys
import threading

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
log = logging.getLogger("mcp")


class Server:
    def __init__(self, cmd: list[str], env: dict[str, str], timeout: float):
        self.timeout = timeout
        self.p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, **env},
            text=True,
            bufsize=1,
        )
        self._id = 0
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _drain_stderr(self):
        for line in self.p.stderr:
            log.info("[server] %s", line.rstrip())

    def notify(self, method: str, params: dict | None = None):
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method,
                                       "params": params or {}}) + "\n")
        self.p.stdin.flush()

    def call(self, method: str, params: dict | None = None):
        self._id += 1
        mid = self._id
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method,
                                       "params": params or {}}) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("server closed stdout")
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                log.info("[non-json] %s", line.rstrip())
                continue
            if msg.get("id") == mid:
                return msg

    def handshake(self):
        r = self.call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "probe", "version": "0"},
        })
        self.notify("notifications/initialized")
        return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True, help="path to the MCP server entrypoint")
    ap.add_argument("--list-tools", action="store_true")
    ap.add_argument("--tool", help="tool name to call")
    ap.add_argument("--args", default="{}", help="JSON arguments for the tool")
    ap.add_argument("--env", action="append", default=[], metavar="K=V")
    ap.add_argument("--timeout", type=float, default=600)
    a = ap.parse_args()

    env = dict(kv.split("=", 1) for kv in a.env)
    s = Server(["node", a.server], env, a.timeout)
    init = s.handshake()
    log.info("server: %s", json.dumps(init.get("result", {}).get("serverInfo", {})))

    if a.list_tools:
        r = s.call("tools/list")
        for t in r["result"]["tools"]:
            print(f"{t['name']}\t{t.get('description', '')[:110]}")
    if a.tool:
        r = s.call("tools/call", {"name": a.tool, "arguments": json.loads(a.args)})
        print(json.dumps(r.get("result", r), ensure_ascii=False, indent=2)[:12000])
    s.p.terminate()


if __name__ == "__main__":
    main()
