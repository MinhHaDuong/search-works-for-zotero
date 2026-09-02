/**
 * Ticket 0576's spawn probe, as it runs INSIDE a host process.
 *
 * The same file is loaded two ways on purpose:
 *   - by `node probe-payload.mjs`            -> the POSITIVE CONTROL, where every arm MUST work;
 *   - by `utilityProcess.fork(...)` from     -> the portable substitute for the way Claude
 *     electron-main.mjs                         Desktop hosts a zoteus server.
 *
 * One file, so a difference in the result is a difference in the host and not a difference
 * in the probe. A probe that cannot spawn anywhere is measuring its own harness.
 *
 * It answers items 1-4 of the ticket. Item 5 (what the host does to the child on quit) is
 * Claude Desktop's own behaviour and is NOT answered here; see the report.
 */
import { spawn } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const CHILD = join(HERE, 'probe-child.mjs');
const MARKER = 'ZOTEUS_PROBE_CHILD';

const OUT = process.env.ZOTEUS_PROBE_OUT;
const EOF_FILE = process.env.ZOTEUS_PROBE_EOF_FILE;
const ARMED_FILE = process.env.ZOTEUS_PROBE_ARMED_FILE;
const HOST_LABEL = process.env.ZOTEUS_PROBE_HOST ?? 'unknown';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const clip = (s, n = 800) => (s.length > n ? `${s.slice(0, n)}\n...[${s.length - n} more chars]` : s);

const alive = (pid) => {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
};

/**
 * Run one spawn arm to completion and report what actually happened, never what was
 * expected. Every field here is an observation; the verdict is assembled by the reader.
 */
async function arm(name, command, args, extraEnv, { duplex = true } = {}) {
  const env = { ...process.env, ZOTEUS_PROBE_CHILD_TTL_MS: '15000', ...extraEnv };
  // ELECTRON_RUN_AS_NODE must be ABSENT, not empty, in the arm that tests its absence:
  // Electron reads presence, and an inherited value would silently make the two arms one.
  if (extraEnv && Object.prototype.hasOwnProperty.call(extraEnv, 'ELECTRON_RUN_AS_NODE') && extraEnv.ELECTRON_RUN_AS_NODE === undefined) {
    delete env.ELECTRON_RUN_AS_NODE;
  }
  delete env.ZOTEUS_PROBE_EOF_FILE; // only the orphan arm's child writes an EOF marker

  const result = {
    arm: name,
    command,
    args,
    electronRunAsNodeInChildEnv: env.ELECTRON_RUN_AS_NODE ?? null,
    spawned: false,
    spawnError: null,
    pid: null,
    helloSeen: false,
    hello: null,
    aliveAfterSpawn: null,
    duplexRounds: 0,
    duplexOk: null,
    exitCode: null,
    exitSignal: null,
    stdout: '',
    stderr: '',
  };

  let child;
  try {
    child = spawn(command, args, { env, stdio: ['pipe', 'pipe', 'pipe'] });
  } catch (e) {
    result.spawnError = `${e?.code ?? ''} ${e?.message ?? String(e)}`.trim();
    return result;
  }

  let out = '';
  let err = '';
  const pongs = new Set();
  child.stdout.on('data', (d) => {
    out += d.toString('utf8');
    for (const line of out.split('\n')) {
      if (!line.startsWith(`${MARKER} `)) continue;
      let obj;
      try {
        obj = JSON.parse(line.slice(MARKER.length + 1));
      } catch {
        continue;
      }
      if (obj.event === 'hello' && !result.helloSeen) {
        result.helloSeen = true;
        result.hello = obj;
      }
      if (obj.event === 'pong') pongs.add(obj.n);
    }
  });
  child.stderr.on('data', (d) => {
    err += d.toString('utf8');
  });

  const exited = new Promise((resolve) => {
    child.on('exit', (code, signal) => {
      result.exitCode = code;
      result.exitSignal = signal;
      resolve();
    });
    child.on('error', (e) => {
      result.spawnError = `${e?.code ?? ''} ${e?.message ?? String(e)}`.trim();
      resolve();
    });
  });

  result.spawned = typeof child.pid === 'number';
  result.pid = child.pid ?? null;

  // Item 1's second half: does the child OUTLIVE the call that made it? Waiting for the
  // announcement first would confound "did not start" with "started and said nothing",
  // which is exactly the pair a GUI launch separates.
  await sleep(1500);
  result.aliveAfterSpawn = result.pid ? alive(result.pid) : false;

  // Item 4, direction by direction: write, then require the answer back.
  if (duplex && result.helloSeen && result.aliveAfterSpawn) {
    for (let n = 1; n <= 3; n += 1) {
      try {
        child.stdin.write(`PING ${n}\n`);
      } catch {
        break;
      }
      await sleep(250);
      if (pongs.has(n)) result.duplexRounds += 1;
    }
    result.duplexOk = result.duplexRounds === 3;
  }

  try {
    child.stdin.write('BYE\n');
  } catch {
    /* the pipe may already be gone */
  }
  await Promise.race([exited, sleep(2500)]);
  if (result.pid && alive(result.pid)) {
    try {
      process.kill(result.pid, 'SIGKILL');
    } catch {
      /* already gone */
    }
    result.killedByProbe = true;
    await Promise.race([exited, sleep(1000)]);
  }

  result.stdout = clip(out);
  result.stderr = clip(err);
  return result;
}

async function main() {
  const report = {
    host: HOST_LABEL,
    at: new Date().toISOString(),
    platform: `${process.platform}-${process.arch}`,
    // Item 2's first half, recorded before any arm runs.
    execPath: process.execPath,
    argv0: process.argv0,
    versions: process.versions,
    isElectronRuntime: typeof process.versions.electron === 'string',
    // 'utility' inside a UtilityProcess, 'browser' in Electron's main process, absent in
    // Node and under ELECTRON_RUN_AS_NODE. It is what proves the harness reproduced the
    // hosting shape it claims to.
    processType: process.type ?? null,
    electronVersion: process.versions.electron ?? null,
    inheritedElectronRunAsNode: process.env.ELECTRON_RUN_AS_NODE ?? null,
    arms: [],
  };

  // Item 2: execPath WITHOUT ELECTRON_RUN_AS_NODE. Under standalone Node this is the
  // ordinary case and must work; under Electron it is the one the hazard names.
  report.arms.push(await arm('execPath-plain', process.execPath, [CHILD], { ELECTRON_RUN_AS_NODE: undefined }));

  // DISCONFOUNDER, Electron only. The arm above can fail for a reason that has nothing to
  // do with the question: on this Linux box Chromium's SUID sandbox helper is not setuid
  // root (kernel.apparmor_restrict_unprivileged_userns=1), so an Electron child aborts at
  // setuid_sandbox_host.cc before it becomes anything at all, and "died" would be read as
  // "launched a GUI". Passing --no-sandbox lets the child get far enough to say which
  // runtime it is. It is NOT added under standalone Node, where node would reject the flag
  // and turn the positive control red for a reason of the probe's own making.
  if (typeof process.versions.electron === 'string') {
    report.arms.push(
      await arm('execPath-plain-no-sandbox', process.execPath, ['--no-sandbox', CHILD], { ELECTRON_RUN_AS_NODE: undefined }),
    );
  }

  // Item 3: the same, with the env var set. Necessary / sufficient / neither is read off
  // the pair, not asserted.
  report.arms.push(await arm('execPath-run-as-node', process.execPath, [CHILD], { ELECTRON_RUN_AS_NODE: '1' }));

  // Availability control: a plain `node` on PATH. It says whether the recipe of last
  // resort exists on THIS machine; it does not say whether it exists inside Claude Desktop.
  report.arms.push(await arm('path-node', 'node', [CHILD], { ELECTRON_RUN_AS_NODE: undefined }));

  // Item 4's second half: does stdin EOF reach the child when the host dies? Arm the
  // orphan with whichever recipe worked, tell the supervisor, and wait to be killed.
  // The orphan must be spawned by the recipe we would actually SHIP, not merely by the
  // first arm that answered. Under Electron the first answering arm is the one that
  // launches a GUI runtime, whose lifecycle is not the one SPEC.md 5.2.5 depends on, so
  // "first hello wins" would measure the wrong process. Order of preference, explicit:
  const PREFERRED = ['execPath-run-as-node', 'path-node', 'execPath-plain-no-sandbox', 'execPath-plain'];
  const winner = PREFERRED.map((n) => report.arms.find((a) => a.arm === n && a.helloSeen)).find(Boolean);
  report.orphanRecipe = winner ? winner.arm : null;
  if (winner && ARMED_FILE && EOF_FILE) {
    const env = { ...process.env, ZOTEUS_PROBE_EOF_FILE: EOF_FILE, ZOTEUS_PROBE_CHILD_TTL_MS: '45000' };
    if (winner.arm === 'execPath-run-as-node') env.ELECTRON_RUN_AS_NODE = '1';
    else delete env.ELECTRON_RUN_AS_NODE;
    const command = winner.arm === 'path-node' ? 'node' : process.execPath;
    const args = winner.arm === 'execPath-plain-no-sandbox' ? ['--no-sandbox', CHILD] : [CHILD];
    const orphan = spawn(command, args, { env, stdio: ['pipe', 'pipe', 'pipe'] });
    await sleep(1500);
    report.orphan = { command, args, pid: orphan.pid ?? null, alive: orphan.pid ? alive(orphan.pid) : false };
    if (OUT) writeFileSync(OUT, JSON.stringify(report, null, 2));
    // The supervisor reads this, kills the host, then looks for the EOF marker.
    writeFileSync(ARMED_FILE, JSON.stringify({ hostPid: process.pid, orphanPid: orphan.pid ?? null }));
    await sleep(40000); // long enough to be killed; bounded so nothing is left running
    return;
  }

  report.orphan = { command: null, pid: null, alive: false, note: 'no arm produced a live child to orphan' };
  if (OUT) writeFileSync(OUT, JSON.stringify(report, null, 2));
  if (ARMED_FILE) writeFileSync(ARMED_FILE, JSON.stringify({ hostPid: process.pid, orphanPid: null }));
}

main().catch((e) => {
  if (OUT) writeFileSync(OUT, JSON.stringify({ host: HOST_LABEL, fatal: String(e?.stack ?? e) }, null, 2));
  process.exit(1);
});
