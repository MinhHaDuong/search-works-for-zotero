/* Can the supervision panel be operated without a mouse? Ticket 0769, action 1.

   Evaluated INSIDE a real Zotero chrome window. That placement is ticket 0769's
   own invariant: the driver may perform gestures, but its readings are not the
   verdict -- these assertions run in the window, against the live DOM.

   Why a separate file rather than more of `sdt-sitter-harness/bootstrap.js`,
   where 0769 files this work: that harness is a whole-flow probe -- it builds a
   fixture library, waits out a sweep, exercises disable/re-enable and asserts
   against all of it, and its keyboard section stops at `summary.focus()` under a
   comment saying it asserts "what can be established without synthesizing key
   events". Synthesizing them needs a window and an armed sitter and nothing
   else, so requiring the rest of that flow would make the one reading 0769 asks
   for the most expensive one to take.

   ## How the keys are delivered, and what that is worth

   Three methods exist and two are unavailable here, which is itself a finding
   worth the file it is written in:

   - `windowUtils.sendKeyEvent` -- what Mozilla's `synthesizeKey` uses. **Gone**
     in the Gecko 140 these Zotero 10 builds ship; only `sendNativeKeyEvent`
     remains on that interface.
   - `sendNativeKeyEvent` -- OS-level, the strongest form. Accepted without
     error and **delivered nothing**: the window reports `hasFocus === false`,
     because nothing on the test display gives it X focus. A native key goes to
     whatever the X server thinks is focused, which is not us.
   - A dispatched `KeyboardEvent` -- what remains. Here it arrives with
     `isTrusted === true`, so it is not obviously the toothless synthetic event
     one would expect, but that is an observation, not a guarantee.

   So the method cannot be assumed to drive the platform's own default actions,
   and this probe does not assume it. `tabMovesFocus` below is a CONTROL run
   before the assertion that depends on it: dispatch Tab, see whether focus
   actually moved. If it did not, the tab-order reading is reported as
   not-established rather than as a pass or a failure -- the distinction
   `tickets/AGENTS.md` insists on, between a thing being absent and a probe
   being unable to see it.

   The Escape assertion needs no such caveat. The panel's own handling is a
   plain `keydown` listener in `bootstrap.js` (around line 2252, added because
   "Escape does nothing unless asked to" -- found live), and a dispatched
   keydown reaches a JS listener whatever its provenance. That assertion
   exercises the shipped code path directly, which is why it is the one the
   driver's `--break-escape` arm can show red. */

(async () => {
  const results = [];
  const notes = {};
  const record = (name, ok, detail) => {
    results.push({ name, result: ok === null ? 'NOT-ESTABLISHED' : (ok ? 'pass' : 'FAIL'),
                   detail: detail ?? null });
    return ok;
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  try {
    const win = Zotero.getMainWindow();
    if (!win) throw new Error('no main window');

    const press = (target, doc, key, extra = {}) => {
      const node = doc.activeElement || doc.documentElement;
      node.dispatchEvent(new target.KeyboardEvent('keydown',
        { key, bubbles: true, cancelable: true, composed: true, ...extra }));
    };

    const button = win.document.getElementById('sdt-pack-sitter-button');
    if (!button) throw new Error('toolbar button absent; is the sitter armed?');

    const panels = () => Array.from(Services.wm.getEnumerator(null))
      .filter((w) => !w.closed && w.document?.getElementById('sdt-status'));

    for (const w of panels()) w.close();
    await sleep(300);

    notes.windowHasFocus = win.document.hasFocus();
    notes.nativeKeysAvailable = typeof win.windowUtils.sendKeyEvent === 'function';

    // --- 1. the toolbar control takes keyboard focus ----------------------
    button.focus();
    await sleep(150);
    const afterFocus = win.document.activeElement;
    record('the toolbar control accepts keyboard focus',
      afterFocus === button || button.contains(afterFocus),
      `activeElement=${afterFocus?.id || afterFocus?.tagName || 'null'}`);

    // --- 2. the panel opens from the keyboard -----------------------------
    // Enter then Space: which one a toolbarbutton answers to is the platform's
    // business. Failing only when NEITHER opens it matches the requirement --
    // reachable without a mouse -- rather than pinning a key this plugin does
    // not choose.
    let panel = null;
    const buttonFocused = win.document.activeElement === button
      || button.contains(win.document.activeElement);
    for (const key of ['Enter', ' ']) {
      if (!buttonFocused) break;  // dispatching at the wrong node proves nothing
      press(win, win.document, key);
      await sleep(700);
      const open = panels();
      if (open.length) { panel = open[0]; notes.openedWith = key === ' ' ? 'Space' : key; break; }
    }
    if (!panel) {
      // Fall back to the command path so the rest of the run still has a panel
      // to read. Recorded as its own line: the keyboard-open reading FAILED,
      // and everything after it was reached another way.
      record('the panel opens from the keyboard',
        buttonFocused ? false : null,
        buttonFocused
          ? 'neither Enter nor Space opened it; opened via doCommand to continue'
          : 'not attempted: the toolbar control never took focus, so a key press '
            + 'would have gone to whatever did. Read the focus line above -- that '
            + 'is the finding, and this reading depends on it.');
      button.doCommand();
      await sleep(900);
      panel = panels()[0] || null;
      if (!panel) {
        return JSON.stringify({ ok: false, results, notes,
          error: 'the panel would not open by any means' });
      }
    } else {
      record('the panel opens from the keyboard', true, `with ${notes.openedWith}`);
    }
    const doc = panel.document;
    await sleep(300);

    // --- 3. the panel places focus inside itself --------------------------
    const inside = doc.activeElement;
    record('the panel places focus inside itself when opened',
      !!inside && inside !== doc.body && doc.contains(inside),
      `activeElement=${inside?.id || inside?.tagName || 'null'}`);

    // --- 4. CONTROL, then the tab-order reading it gates ------------------
    const summaries = Array.from(doc.querySelectorAll('details > summary'));
    notes.summaryOf = summaries.map((s) => s.parentNode?.id || '(unnamed)');
    const before = doc.activeElement;
    press(panel, doc, 'Tab');
    await sleep(200);
    const tabMovesFocus = doc.activeElement !== before;
    notes.tabMovesFocus = tabMovesFocus;

    if (!tabMovesFocus) {
      // The probe cannot see this, which is not the same as the panel failing
      // it. Say so, and say what would settle it.
      record('every disclosure summary is reachable by Tab', null,
        'a dispatched Tab does not move focus in this build, so tab ORDER is '
        + 'not observable from here; each summary does accept focus '
        + 'programmatically (asserted below). Settling it needs a focused '
        + 'window and sendNativeKeyEvent, i.e. a session with X focus.');
      // Open every ancestor first. Four of the five disclosures are nested
      // inside `sdt-details`, which ships closed, and an element inside a
      // closed <details> is not rendered and cannot take focus. Testing them
      // shut measured the markup's nesting and reported it as the panel
      // refusing focus -- the probe's defect, caught by reading the nesting
      // rather than believing the first red run.
      for (const summary of summaries) {
        for (let d = summary.parentElement; d; d = d.parentElement?.closest('details')) {
          if (d.tagName.toLowerCase() === 'details') d.open = true;
        }
      }
      await sleep(200);
      for (const summary of summaries) {
        // A disclosure the panel has deliberately hidden is not a disclosure
        // that refuses focus. `fillSDTNotIndexed` sets `section.hidden = true`
        // when a completed census finds nothing outstanding -- SPEC.md
        // §5.2.7's "empty groups and an entirely empty section are hidden" --
        // and an element inside `hidden` is not rendered, so it cannot take
        // focus and must not be asked to.
        //
        // This probe reported that as a hard FAIL until review caught it. The
        // runs that passed had simply been taken while the census was still in
        // flight, with the section still on screen: a green that came from
        // timing rather than from the panel being right, which is the exact
        // confusion this file exists to prevent elsewhere. A reading whose
        // subject is not on screen is NOT-ESTABLISHED, and says which.
        const hiddenBy = (() => {
          for (let n = summary; n && n !== doc.body; n = n.parentElement) {
            if (n.hidden) return n.id || n.tagName;
          }
          return null;
        })();
        const id = summary.parentNode?.id || 'unnamed';
        if (hiddenBy) {
          record(`the ${id} summary accepts focus`, null,
            `not on screen: hidden by ${hiddenBy}. A hidden disclosure cannot `
            + 'take focus and is not asked to; this says nothing about the '
            + 'panel, only that this run had nothing to show there.');
          continue;
        }
        summary.focus();
        await sleep(60);
        record(`the ${id} summary accepts focus`,
          doc.activeElement === summary,
          `activeElement=${doc.activeElement?.id || doc.activeElement?.tagName}`);
      }
      for (const summary of summaries) {
        const d = summary.parentElement;
        if (d && d.tagName.toLowerCase() === 'details') d.open = false;
      }
    } else {
      const wanted = new Set(summaries);
      const seen = new Set();
      for (let i = 0; i < 40 && seen.size < wanted.size; i++) {
        press(panel, doc, 'Tab');
        await sleep(60);
        if (wanted.has(doc.activeElement)) seen.add(doc.activeElement);
      }
      record('every disclosure summary is reachable by Tab',
        summaries.length > 0 && seen.size === wanted.size,
        `${seen.size}/${summaries.length} reached within 40 tab stops`);
    }

    // --- 5. Escape closes the panel ---------------------------------------
    // The assertion with no caveat: the handler under test is JS, and a
    // dispatched keydown reaches it exactly as a real one would.
    doc.documentElement.dispatchEvent(new panel.KeyboardEvent('keydown',
      { key: 'Escape', bubbles: true, cancelable: true, composed: true }));
    await sleep(800);
    const closed = panel.closed || panels().length === 0;
    record('Escape closes the panel', closed,
      closed ? null : 'still open 800ms after Escape');

    // --- 6. focus returns to the toolbar control --------------------------
    // Easiest to lose and worst to lose: a panel that closes without restoring
    // focus strands a keyboard user with no indication of where they are.
    await sleep(300);
    const returned = win.document.activeElement;
    record('focus returns to the toolbar control after Escape',
      returned === button || button.contains(returned),
      `activeElement=${returned?.id || returned?.tagName || 'null'}`);

    notes.zoteroVersion = Zotero.version;
    notes.toolbarAccessibleName = button.getAttribute('aria-label');
    notes.reducedMotionPreferred =
      win.matchMedia('(prefers-reduced-motion: reduce)').matches;

    return JSON.stringify({
      ok: results.every((r) => r.result !== 'FAIL'),
      established: results.every((r) => r.result === 'pass'),
      results, notes,
    });
  } catch (error) {
    return JSON.stringify({ ok: false, results, notes,
      error: String(error && error.stack ? error.stack : error) });
  }
})()
