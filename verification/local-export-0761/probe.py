#!/usr/bin/env python3
"""Read-only local export probe; emit no library identifiers or content.

Run with desktop Zotero open. Responses stay in memory; stdout is sanitized JSON.
"""
import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

BASE = 'http://127.0.0.1:23119/api/users/0'
FORMATS = ('bibtex biblatex ris csljson csv mods tei coins rdf_bibliontology '
           'rdf_dc rdf_zotero refer wikipedia bookmarks').split()


def get(path, **params):
    try:
        with urlopen(BASE + path + '?' + urlencode(params), timeout=60) as response:
            return response.status, response.read(), response.headers.get('Zotero-Version')
    except HTTPError as error:
        return error.code, error.read(), None


def items(path, **params):
    status, body, _ = get(path, **params)
    if status != 200:
        raise RuntimeError(f'Discovery failed: HTTP {status}')
    return json.loads(body)


sample = items('/items/top', limit=100)
parents = [x for x in sample if x['data']['itemType'] not in ('attachment', 'note', 'annotation')]
parent = parents[0]
key = parent['key']
rows = []
for fmt in FORMATS:
    status, body, version = get('/items/top', itemKey=key, format=fmt)
    rows.append({'case': 'format_' + fmt, 'status': status, 'nonempty': bool(body.strip())})


def selection(name, path, **params):
    expected = items(path, **params)
    status, body, _ = get(path, format='csljson', **params)
    row = {'case': name, 'status': status}
    if status == 200:
        actual = json.loads(body)
        # CSL titles are compared only in memory, never emitted.
        expected_titles = sorted(x['data'].get('title', '') for x in expected
                                 if x['data']['itemType'] not in ('note', 'annotation'))
        actual_titles = sorted(x.get('title', '') for x in actual)
        row.update(json_count=len(expected), export_count=len(actual),
                   titles_match_json=actual_titles == expected_titles,
                   bare_array=isinstance(actual, list))
    rows.append(row)


selection('keyed_parent', '/items/top', itemKey=key)
selection('limit', '/items', limit=1)
selection('item_type', '/items', itemType=parent['data']['itemType'], limit=3)
selection('query', '/items', q=parent['data'].get('title', ''), limit=3)
selection('query_no_match', '/items', q='zoteus-probe-no-match-0742-6b4ff25c', limit=3)
selected = next((x for x in parents if x['data'].get('collections')), None)
if selected:
    collection = selected['data']['collections'][0]
    selection('collection', '/collections/' + collection + '/items', limit=3)
    selection('collection_keyed', '/collections/' + collection + '/items/top', itemKey=selected['key'])
    selection('collection_query_type', '/collections/' + collection + '/items',
              q=selected['data'].get('title', ''), itemType=selected['data']['itemType'], limit=3)
else:
    rows.append({'case': 'collection', 'skipped': 'No collected parent in discovery sample'})
child = None
for candidate in parents[:20]:
    children = items('/items/' + candidate['key'] + '/children', limit=10)
    child = next((x for x in children if x['data']['itemType'] == 'attachment'), None)
    if child:
        selection('parent_with_attachment', '/items/top', itemKey=candidate['key'])
        selection('child_key_only', '/items/top', itemKey=child['key'])
        break
if not child:
    rows.append({'case': 'child_key_only', 'skipped': 'No attachment in discovery sample'})
status, body, version = get('/items/top', itemKey=key, format='not-a-format')
rows.append({'case': 'unsupported_format', 'status': status,
             'mentions_invalid_format': bool(re.search(rb'Invalid.*format|format.*Invalid', body, re.I))})
print(json.dumps({'observed_at': datetime.now(timezone.utc).isoformat(),
                  'zotero_version': version, 'transport': 'loopback HTTP; no cloud key',
                  'rows': rows}, indent=2))
