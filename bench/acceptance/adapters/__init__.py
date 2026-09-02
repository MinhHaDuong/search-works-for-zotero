"""One thin declaration per target, and nothing an assertion may import.

The split `bench/acceptance/__init__.py` describes: `interface.py` is the
vocabulary, `assertions.py` phrases clauses over it, and every target's name
lives here and only here. An adapter carries its declaration and the minimal
transport needed to invoke the surfaces it declares — no patch or workaround, no
non-default option, no access unavailable to the target's own users, and no
scoring of a result (`SPEC.md` §5.2.8; `DECISIONS.md`, ratified 2026-09-02).

Nothing is imported here on purpose. A target's adapter reaches for that
target's transport, and a module that imported them all would make the cheapest
question in the layer — can this declaration be read without the target
installed? — depend on every target at once.
"""
