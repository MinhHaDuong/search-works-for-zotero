"""Committed fixture generators.

A package rather than a loose directory for one reason: `bench/check_deps.py`
reads `__init__.py` to decide whether an imported name is ours or a dependency,
and a test importing `fixtures.make_attachment_fixtures` would otherwise be read
as importing an undeclared third-party package named `fixtures`.
"""
