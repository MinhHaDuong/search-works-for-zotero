#!/usr/bin/env node
/**
 * The spawned child of ticket 0576's spawn probe.
 *
 * It has three jobs and no others. It ANNOUNCES what runtime actually started it, so the
 * parent can tell a Node process from an Electron GUI that merely accepted the argument.
 * It ECHOES, so the full-duplex stdio pipe SPEC.md 5.2.5 requires is exercised in both
 * directions rather than assumed from a successful spawn. And it RECORDS its own stdin
 * EOF to a file, because that is the orphan-repair signal the topology depends on and the
 * only way to observe it is from a process that outlives its parent.
 *
 * Everything it writes to stdout is one JSON object per line behind a marker, so a GUI's
 * incidental chatter cannot be mistaken for the child's own voice.
 */
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const fs = require('node:fs');

const MARKER = 'ZOTEUS_PROBE_CHILD';
const eofPath = process.env.ZOTEUS_PROBE_EOF_FILE;

const emit = (obj) => {
  process.stdout.write(`${MARKER} ${JSON.stringify(obj)}\n`);
};

emit({
  event: 'hello',
  pid: process.pid,
  ppid: process.ppid,
  execPath: process.execPath,
  argv: process.argv,
  versions: process.versions,
  // The one env var whose presence or absence is the whole of probe item 3.
  electronRunAsNode: process.env.ELECTRON_RUN_AS_NODE ?? null,
  // Electron sets process.versions.electron in every process it runs, main, renderer and
  // utility alike; a standalone Node never has it (upstream
  // src/features/search/electron.ts:47-54). So this is what says the binary was Electron.
  isElectronRuntime: typeof process.versions.electron === 'string',
  // ...and this is what says which MODE it started in, which is the distinction the whole
  // probe turns on. Electron's main process reports process.type === 'browser'; a process
  // started under ELECTRON_RUN_AS_NODE has no process.type at all, because it is Node.
  // versions.electron alone cannot separate the two: it is set in both.
  processType: process.type ?? null,
});

// Full duplex: every PING that arrives on stdin is answered on stdout.
let buf = '';
process.stdin.on('data', (chunk) => {
  buf += chunk.toString('utf8');
  let nl;
  while ((nl = buf.indexOf('\n')) !== -1) {
    const line = buf.slice(0, nl).trim();
    buf = buf.slice(nl + 1);
    if (line.startsWith('PING ')) emit({ event: 'pong', n: Number(line.slice(5)) });
    else if (line === 'BYE') process.exit(0);
  }
});

// The orphan-repair signal. Written to a FILE rather than to stdout on purpose: when the
// host dies, the pipe this child would otherwise report on is exactly what died with it.
const recordEof = (how) => {
  if (!eofPath) return;
  try {
    fs.writeFileSync(eofPath, JSON.stringify({ how, at: new Date().toISOString(), pid: process.pid }));
  } catch {
    /* there is nothing left to report it to */
  }
};

process.stdin.on('end', () => {
  recordEof('stdin-end');
  process.exit(0);
});
process.stdin.on('close', () => {
  recordEof('stdin-close');
  process.exit(0);
});

// Stay alive long enough to be observed outliving the spawn call, and long enough for the
// supervisor to kill the host over us. Bounded, so a failed run leaves nothing behind.
const ttl = Number(process.env.ZOTEUS_PROBE_CHILD_TTL_MS ?? 60000);
setTimeout(() => {
  emit({ event: 'ttl-expired' });
  process.exit(0);
}, ttl);
