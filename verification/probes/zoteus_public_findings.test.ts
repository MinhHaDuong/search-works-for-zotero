// Read-only defect reproductions for ticket 0736, against upstream 5a81cee.
// Copy into <zoteus>/tests/features/public-findings.test.ts and run:
// npm test -- tests/features/public-findings.test.ts --maxWorkers=1 --minWorkers=1
// These assertions pin observed defects, not desired post-fix behavior.
import { describe, it, expect, vi } from 'vitest';
import { createSearchIndex, nodeSqliteAvailable } from '../../src/features/search/factory.js';
import { PAGE_SIZE, startIndexBuild, startIndexUpdate } from '../../src/features/search/build.js';
import { loadConfig } from '../../src/config.js';
import type { SearchIndex } from '../../src/features/search/backend.js';
import { LibraryRouter } from '../../src/router/library-router.js';
import createItems from '../../src/tools/create-items.js';
import annotate from '../../src/tools/annotate.js';
import bibliography from '../../src/tools/bibliography.js';
import formatBibliography from '../../src/tools/format-bibliography.js';
import { WebApiClient } from '../../src/api/web-client.js';
import { RateLimitedFetcher } from '../../src/api/http.js';
// FakeLibrary and setup below adapted from upstream search-own-words.test.ts.
const silentLogger = { debug() {}, info() {}, warn() {}, error() {} };
const backends: Array<'memory' | 'sqlite'> = nodeSqliteAvailable() ? ['memory', 'sqlite'] : ['memory'];

interface Row {
  key: string;
  version: number;
  data: any;
}

/**
 * A Zotero library with children in it: items, their attachments, the notes hanging off
 * items and the annotations hanging off attachments — each with its own version in the
 * library's one sequence, which is what makes the update path testable at all.
 */
class FakeLibrary {
  version = 0;
  readonly rows = new Map<string, Row>();

  private write(key: string, data: any): void {
    this.version++;
    this.rows.set(key, { key, version: this.version, data: { key, ...data } });
  }

  item(key: string, title: string, abstractNote = ''): void {
    this.write(key, { itemType: 'journalArticle', title, abstractNote });
  }

  attachment(key: string, parentItem: string): void {
    this.write(key, { itemType: 'attachment', title: 'PDF', parentItem });
  }

  note(key: string, parentItem: string, note: string): void {
    this.write(key, { itemType: 'note', note, parentItem });
  }

  standaloneNote(key: string, note: string): void {
    this.write(key, { itemType: 'note', note });
  }

  annotation(key: string, parentItem: string, text: string, comment = ''): void {
    this.write(key, {
      itemType: 'annotation',
      annotationType: 'highlight',
      annotationText: text,
      annotationComment: comment,
      parentItem,
    });
  }

  remove(key: string): void {
    this.version++;
    this.rows.delete(key);
  }

  private matching(q: any): Row[] {
    let rows = [...this.rows.values()];
    if (q.itemType) {
      const types = String(q.itemType).split('||').map((t) => t.trim());
      rows = rows.filter((r) => types.includes(r.data.itemType));
    }
    if (q.itemKey) {
      const keys = String(q.itemKey).split(',');
      rows = rows.filter((r) => keys.includes(r.key));
    }
    // `/items/top` is the crawl a build makes: regular items and standalone notes, never
    // anything with a parent.
    if (q.top) rows = rows.filter((r) => !r.data.parentItem);
    if (q.since) rows = rows.filter((r) => r.version > q.since);
    return rows;
  }

  /** Router double: only the reads a build and an update make. */
  router() {
    return {
      servesLocally: vi.fn(() => false),
      defaultLibrary: () => ({ type: 'user' as const, id: 1 }),
      searchItems: vi.fn(async (q: any) => {
        const rows = this.matching(q);
        const start = q.start ?? 0;
        return {
          data: rows.slice(start, start + (q.limit ?? PAGE_SIZE)).map((r) => ({ key: r.key, data: r.data })),
          totalResults: rows.length,
          lastModifiedVersion: this.version,
        };
      }),
      itemVersions: vi.fn(async (q: any) => {
        const rows = this.matching(q);
        const start = q.start ?? 0;
        const page = rows.slice(start, start + (q.limit ?? 5000));
        return {
          versions: Object.fromEntries(page.map((r) => [r.key, r.version])),
          totalResults: rows.length,
          lastModifiedVersion: this.version,
        };
      }),
      fullTextSince: vi.fn(async () => ({})),
      getFullText: vi.fn(async () => null),
    };
  }
}

async function settle(search: SearchIndex): Promise<void> {
  for (let i = 0; i < 800 && search.buildStatus().state === 'building'; i++) {
    await new Promise((r) => setTimeout(r, 2));
  }
}

function makeCtx(search: SearchIndex, router: any, env: Record<string, string> = {}): any {
  return { config: loadConfig(env as any), search, router, logger: silentLogger, searchIndexPath: '' };
}

/** A library with one annotated, one noted and one bare item, indexed. */
async function indexed(backend: 'memory' | 'sqlite', env: Record<string, string> = {}) {
  const lib = new FakeLibrary();
  lib.item('AAAAAAAA', 'Coastal erosion', 'shoreline retreat rates');
  lib.attachment('ATTACHAA', 'AAAAAAAA');
  lib.annotation('ANNOTAA1', 'ATTACHAA', 'sediment budgets are unreliable', 'this contradicts Nakamura entirely');
  lib.item('BBBBBBBB', 'Urban heat', 'city temperature anomalies');
  lib.note('NOTEBBB1', 'BBBBBBBB', '<div class="zotero-note"><p>My own <strong>objection</strong>: the albedo assumption is doing all the work.</p></div>');
  lib.item('CCCCCCCC', 'Nothing hangs off this one', 'a bare item');
  const search = await createSearchIndex({ embedder: null, logger: silentLogger, backend, jsonPath: '' });
  const router = lib.router();
  const ctx = makeCtx(search, router, env);
  startIndexBuild(ctx);
  await settle(search);
  return { lib, search, router, ctx };
}


describe('public routing findings', () => {
  it('writes to personal library despite a configured group default', async () => {
    const config = loadConfig({ ZOTERO_LIBRARY_TYPE: 'group', ZOTERO_LIBRARY_ID: '456' } as any);
    const capabilities: any = { cloud: { userID: 123 }, localApi: false };
    const writeItems = vi.fn(async (_lib: any, _items: any[]) => ({successful: [], failed: [], newLibraryVersion: 1}));
    const web: any = { writeItems };
    const router = new LibraryRouter({config, capabilities, web});
    expect(router.defaultLibrary()).toEqual({type: 'group', id: 456});
    await createItems.handler({items: [{itemType: 'book', title: 'routing probe'}]}, {
      config, capabilities, web, router,
      schema: {validateItem: async () => ({valid: true})},
    } as any);
    expect(writeItems.mock.calls[0]?.[0]).toEqual({type: 'user', id: 123});
  });

  it('looks up an explicit group annotation parent in the default personal library', async () => {
    const config = loadConfig({} as any);
    const capabilities: any = {cloud: {userID: 123}, localApi: false};
    const getItem = vi.fn(async (lib: any) => {
      if (lib.type !== 'group' || lib.id !== 456) throw new Error('fixture 404: wrong library');
      return {data: {key: 'PDFGROUP', itemType: 'attachment', contentType: 'application/pdf'}};
    });
    const writeItems = vi.fn();
    const web: any = {getItem, writeItems};
    const router = new LibraryRouter({config, capabilities, web});
    await expect(annotate.handler({
      parent: 'PDFGROUP', library_type: 'group', library_id: 456,
      annotations: [{type: 'note', comment: 'routing probe', page: 0}],
    }, {config, capabilities, router, web} as any)).rejects.toThrow('fixture 404');
    expect(getItem.mock.calls[0]?.[0]).toEqual({type: 'user', id: 123});
    expect(writeItems).not.toHaveBeenCalled();
  });

  it.each([bibliography, formatBibliography])('$name sends local item keys to cloud users/0', async (tool) => {
    const seen: string[] = [];
    const fetcher = new RateLimitedFetcher({fetchImpl: async (url: any) => {
      seen.push(String(url));
      return new Response('Invalid user ID', {status: 400});
    }});
    const web = new WebApiClient({fetcher});
    const config = loadConfig({ZOTEUS_LOCAL: 'on'} as any);
    const capabilities: any = {cloud: null, localApi: true};
    const local: any = {getItem: vi.fn()};
    const router = new LibraryRouter({config, capabilities, web, local});
    expect(router.servesLocally()).toBe(true);
    await expect(tool.handler({item_keys: ['LOCALKEY']}, {
      router, web, local, capabilities, config,
    } as any)).rejects.toThrow();
    expect(seen).toHaveLength(1);
    expect(seen[0]).toMatch(/^https:\/\/api.zotero.org\/users\/0\/items\?/);
  });
});

describe.each(backends)('public search findings (%s)', (backend) => {
  it('loses retry eligibility after a transient child-version census failure', async () => {
    const {lib, search, router, ctx} = await indexed(backend);
    try {
      const before = search.buildStatus().libraryVersion;
      lib.note('NOTEBBB1', 'BBBBBBBB', '<p>quasarrevision</p>');
      lib.note('NOTEBBB2', 'BBBBBBBB', '<p>nebulaaddition</p>');
      const itemVersions = router.itemVersions.getMockImplementation()!;
      let failOnce = true;
      router.itemVersions.mockImplementation(async (q: any) => {
        if (q.itemType && failOnce) {failOnce = false; throw new Error('transient census outage');}
        return itemVersions(q);
      });
      startIndexUpdate(ctx, {type: 'user', id: 1});
      await settle(search);
      expect(search.buildStatus().state).toBe('done');
      expect(search.buildStatus().libraryVersion).toBe(lib.version);
      expect(lib.version).toBeGreaterThan(before!);
      startIndexUpdate(ctx, {type: 'user', id: 1});
      await settle(search);
      expect(search.buildStatus().state).toBe('done');
      expect(await search.query('quasarrevision', {mode: 'keyword'})).toEqual([]);
      expect(await search.query('nebulaaddition', {mode: 'keyword'})).toEqual([]);
      expect((await search.query('albedo', {mode: 'keyword'})).map(h => h.itemKey)).toEqual(['BBBBBBBB']);
    } finally { await search.close(); }
  });

  it('exhausts the passage pool before item deduplication despite more relevant items', async () => {
    const lib = new FakeLibrary();
    lib.item('AAAAAAAA', 'Heavily annotated paper');
    lib.attachment('ATTACHAA', 'AAAAAAAA');
    for (let i=0; i<40; i++) lib.annotation(`ANN${String(i).padStart(5, '0')}`, 'ATTACHAA', 'topmatch quasar');
    for (const key of ['BBBBBBBB', 'CCCCCCCC', 'DDDDDDDD', 'EEEEEEEE']) lib.item(key, `quasar ${key}`);
    const embedder: any = {
      id: 'fixture', dimensions: 2,
      embed: async (texts: string[], kind: string) => texts.map(t =>
        kind === 'query' || t.includes('topmatch') ? [1, 0] : [0.8, 0.6]),
    };
    const search = await createSearchIndex({embedder, backend, jsonPath: '', logger: silentLogger});
    try {
      const ctx = makeCtx(search, lib.router());
      startIndexBuild(ctx);
      await settle(search);
      expect(search.buildStatus().state).toBe('done');
      expect((await search.query('quasar', {mode: 'semantic', limit: 5})).map(h=>h.itemKey)).toEqual(['AAAAAAAA']);
      const wider = await search.query('quasar', {mode: 'semantic', limit: 20});
      expect(new Set(wider.map(h=>h.itemKey)).size).toBe(5);
    } finally {await search.close();}
  });
});
