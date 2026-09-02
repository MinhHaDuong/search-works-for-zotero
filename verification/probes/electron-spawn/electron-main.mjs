/**
 * The minimal Electron host for ticket 0576's portable arm.
 *
 * It exists to reproduce ONE property of Claude Desktop: that the server runs inside an
 * Electron `UtilityProcess` on Electron's embedded Node rather than as its own program.
 * Upstream established that shape by detecting the host through Electron's UtilityProcess
 * (src/features/search/electron.ts, read in verification/UPSTREAM-1.12.0-REREAD.md), and
 * it is the shape every spawn in SPEC.md 5.2.5 has to work from.
 *
 * It opens no window. A window would add a renderer, a GPU process and a compositor to the
 * measurement, none of which is what the probe is about.
 */
import { app, utilityProcess } from 'electron';
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const PAYLOAD = join(HERE, 'probe-payload.mjs');
const HOST_FILE = process.env.ZOTEUS_PROBE_HOST_FILE;

// Neither is a property of the host under test; both are properties of THIS Linux box, and
// they are recorded rather than hidden. Unprivileged user namespaces are refused here (the
// same refusal that made `unshare -rn` unusable for the egress probe), so Electron's
// sandbox cannot start, and there is no GPU to accelerate with.
app.commandLine.appendSwitch('no-sandbox');
app.disableHardwareAcceleration();

app.whenReady().then(() => {
  if (HOST_FILE) {
    writeFileSync(
      HOST_FILE,
      JSON.stringify(
        {
          mainPid: process.pid,
          electron: process.versions.electron,
          chrome: process.versions.chrome,
          node: process.versions.node,
          execPath: process.execPath,
        },
        null,
        2,
      ),
    );
  }

  const child = utilityProcess.fork(PAYLOAD, [], {
    stdio: 'inherit',
    env: { ...process.env, ZOTEUS_PROBE_HOST: 'electron-utilityprocess' },
  });

  child.on('exit', (code) => {
    process.stderr.write(`[harness] utility process exited ${code}\n`);
    app.quit();
  });
});

// No window is ever opened, so this would otherwise fire the moment one closed.
app.on('window-all-closed', () => {});
