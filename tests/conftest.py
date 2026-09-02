"""Marker registry for the suite.

`make check-fast` runs `pytest tests/ -q` with no `-m` filter, so a marker here classifies
a test by cost rather than selecting it. That is still worth writing down: an unregistered
mark warns on every run, and the tier a test belongs to is the first thing someone splitting
this gate will need.
"""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: spawns a subprocess (node, a driver) — costlier than the pure tier",
    )
