// Paste this into Zotero's Tools -> Developer -> Run JavaScript dialog
// (implemented in chrome/content/zotero/runJS.js; its `run()` does
// `var win = Zotero.getMainWindow(); win.eval(code)`, i.e. this runs with
// the full chrome privilege of the main window -- no plugin, no restart) to
// open a real Firefox RDP listener in an ALREADY-RUNNING Zotero, so
// bench/zotero_rdp_client.py can attach to it.
//
// Ticket 0766. This is a line-by-line replica of what the
// `--start-debugger-server` command-line flag itself runs --
// modules/DevToolsStartup.sys.mjs, handleDevToolsServerFlag() -- extracted
// from Zotero 10.0.2's own omni.ja rather than guessed. The flag's own gate,
// _isRemoteDebuggingEnabled(), requires two prefs to be true:
// "devtools.debugger.remote-enabled" (false by default, greprefs.js:1515)
// and "devtools.chrome.enabled" (already true by Zotero's own default,
// defaults/preferences/zotero.js:1518, so only the first needs setting).
// Setting a pref at runtime via Services.prefs needs no restart; nothing
// else in the flag's own code is restart-only.
//
// A THIRD pref matters and is not part of the flag's own gate: every socket
// accept goes through shared/security/socket.js's per-connection
// `_authenticate()`, which by default shows a server-side "allow this
// connection?" prompt (shared/security/auth.js, the `Prompt` authenticator,
// `devtools.debugger.prompt-connection` -- true by default, greprefs.js:1511)
// before the hello packet is ever sent. In a headless or unattended run
// there is nothing to click, so the client sees the TCP connection accepted
// and then silence -- no hello, ever -- rather than a clean error. This was
// caught empirically validating this file against a live Zotero (ticket
// 0766's log), not by reading the flag's own code, which never mentions it.
// Setting this pref false skips the prompt and answers ALLOW automatically
// (`auth.js`'s `authenticate()` short-circuits to `AuthenticationResult.ALLOW`
// before ever calling `allowConnection`).
//
// Do NOT run this against a Zotero you cannot also quit and restart if
// something goes wrong -- with the prompt disabled this opens a real,
// UNAUTHENTICATED TCP listener with `allowChromeProcess = true`, i.e. full
// chrome-privileged eval, on the given port, to anyone who can reach it. The
// transport is plaintext and the sole listener bound to `port`. Prefer
// binding to loopback only (the default `SocketListener` behavior here) and
// running it on a session you are watching.
//
// After this runs, `python3 bench/zotero_rdp_client.py 'JSON.stringify(1+1)'`
// (default port 6000) should print `"2"`.

(function armDevToolsServer(port) {
  Services.prefs.setBoolPref("devtools.debugger.remote-enabled", true);
  // devtools.chrome.enabled is already true in Zotero's own defaults, but
  // setting it here too costs nothing and makes this snippet self-contained
  // if ever run against a build whose defaults differ.
  Services.prefs.setBoolPref("devtools.chrome.enabled", true);
  // Without this, the connection hangs forever waiting for a UI prompt that
  // nothing will ever answer -- see the note above.
  Services.prefs.setBoolPref("devtools.debugger.prompt-connection", false);

  const {
    useDistinctSystemPrincipalLoader,
  } = ChromeUtils.importESModule(
    "resource://devtools/shared/loader/DistinctSystemPrincipalLoader.sys.mjs",
    { global: "shared" }
  );

  // `requester` is only used as a Set membership key by the loader cache
  // (DistinctSystemPrincipalLoader.sys.mjs); any object identity works.
  const requester = {};
  const serverLoader = useDistinctSystemPrincipalLoader(requester);
  const { DevToolsServer } = serverLoader.require(
    "resource://devtools/server/devtools-server.js"
  );
  const { SocketListener } = serverLoader.require(
    "resource://devtools/shared/security/socket.js"
  );

  DevToolsServer.init();
  // Keep the server alive after the first client disconnects, so a second
  // install/replace/disable/enable cycle in the same experiment can
  // reconnect without re-arming.
  DevToolsServer.keepAlive = true;
  DevToolsServer.registerAllActors();
  // Required for root.js's getProcess(id) to hand out the parent-process
  // descriptor at all -- see server/actors/root.js, getProcess().
  DevToolsServer.allowChromeProcess = true;

  const listener = new SocketListener(DevToolsServer, {
    portOrPath: port,
    webSocket: false,
  });
  listener.open();

  return `RDP server listening on port ${port}`;
})(6000);
