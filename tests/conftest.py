"""Marker registry for the suite.

`make check-fast` selects the `precommit` tests. `make check-full` runs the
complete suite. Other markers classify tests by cost for explicit runs.
"""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "precommit: quick guard tests selected by make check-fast",
    )
    config.addinivalue_line(
        "markers",
        "integration: spawns a subprocess (node, a driver) — costlier than the pure tier",
    )
    config.addinivalue_line(
        "markers",
        "slow: reads real data off the host — an installed Zotero, a model, a large archive — "
        "so it skips where that is absent rather than passing",
    )
