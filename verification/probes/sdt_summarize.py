"""Summarize the SDT campaign and check all successful extraction digests."""
import argparse
import json
from pathlib import Path
import statistics

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('results', type=Path)
args = parser.parse_args()
root = args.results
campaign = json.loads((root / 'campaign/campaign.json').read_text())
configurations = {}
digests = {}
for row in campaign:
    if row.get('kind') == 'batch':
        entries = row['workers']
    else:
        entries = [row]
    for entry in entries:
        data = json.loads((root / 'campaign' / f"{entry['name']}.json").read_text())
        for extraction in data['results']:
            if extraction['errors'] or not extraction['calls']:
                raise RuntimeError(f"Invalid extraction in {entry['name']}")
            key = extraction['sourceHash']
            digests.setdefault(key, set()).add(extraction['structureSha256'])
        if row.get('kind') != 'batch':
            measured = [r for r in data['results'] if not r['warmup']]
            configuration = f"{entry['backend']}-t{entry['threads']}"
            configurations.setdefault(configuration, []).append({
                'document': entry['name'].split('-')[0],
                'pages': measured[0]['pageCount'],
                'wallMs': statistics.median(r['wallMs'] for r in measured),
                'inferenceMs': statistics.median(r['inferenceMs'] for r in measured),
                'maxRssKiB': data['maxRssKiB'],
            })
serial = {key: {'documents': rows,
                'sumMedianWallSeconds': sum(r['wallMs'] for r in rows) / 1000,
                'sumMedianInferenceSeconds': sum(r['inferenceMs'] for r in rows) / 1000}
          for key, rows in configurations.items()}
batch = {}
for jobs in [1, 2, 4, 8, 12]:
    rows = [r for r in campaign if r.get('kind') == 'batch' and r['jobs'] == jobs]
    if len(rows) != 3:
        raise RuntimeError(f'Incomplete batch configuration: {jobs}')
    totals = []
    for row in rows:
        total = 0
        for worker in row['workers']:
            data = json.loads((root / 'campaign' / f"{worker['name']}.json").read_text())
            total += sum(r['pageCount'] for r in data['results'])
        totals.append(total)
    if len(set(totals)) != 1:
        raise RuntimeError('Batch page counts differ')
    seconds = statistics.median(r['wallSeconds'] for r in rows)
    batch[str(jobs)] = {'wallSeconds': seconds, 'runsSeconds': [r['wallSeconds'] for r in rows],
                       'pages': totals[0], 'pagesPerSecond': totals[0] / seconds}
for row in batch.values():
    row['speedup'] = batch['1']['wallSeconds'] / row['wallSeconds']
result = {'serial': serial, 'batch': batch,
          'outputIdentity': {key: sorted(value) for key, value in digests.items()},
          'allOutputsIdentical': all(len(value) == 1 for value in digests.values())}
for backend in ['cpu', 'cuda']:
    path = root / f'python-replay-{backend}.json'
    if path.exists():
        data = json.loads(path.read_text())
        result.setdefault('replay', {})[backend] = {
            'medianMs': statistics.median(row['sumMs'] for row in data['rows'] if not row['warmup']),
            'maxAbsError': max(row['maxAbsError'] for row in data['rows']),
            'ortVersion': data['ortVersion'],
        }
(root / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
