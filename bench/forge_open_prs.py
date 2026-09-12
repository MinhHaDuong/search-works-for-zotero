#!/usr/bin/env python3
"""What `check_sitter_version.py` rule 3 asks the forge, and the only file that
knows this forge is GitHub. Ticket 0779.

THE PROTOCOL, three forms, answered about the repository whose working tree is
the current directory:

    forge_open_prs.py                   one OPEN pull-request number per line
    forge_open_prs.py <number>          that pull request's head commit sha
    forge_open_prs.py <number> <path>   the bytes of <path> at that head

    exit 0   answered; stdout is the answer
    exit 3   that head does not carry that path — a real absence
    exit 1   could not look: no forge remote, no network, no credentials, a
             refusal, a rate limit, an answer in a shape this cannot read

Two exit codes for two different nothings, because conflating them is the whole
defect this ticket exists for: an absence is a fact about the payload, and a
refusal is a fact about the observer. The caller turns exit 1 into NOT-RUN and
exit 3 into "that revision carries no payload", and neither into a green.

WHY THREE FORMS AND NOT ONE. `tickets/AGENTS.md` records the trap in its
GitHub-CLI spelling — `gh pr list --json files` does not populate `files`, so a
one-shot list-plus-filter answers empty whatever the pull requests contain, and
"no collision" is then indistinguishable from "I never looked". The remedy there
is to enumerate and then query each pull request; here that remedy is the
protocol itself, so a caller CANNOT express the one-shot form. The first form
answers only with numbers — it carries no payload information to filter on — and
every fact about a head has to be asked for one pull request at a time.

An empty answer to the first form is therefore a claim, not a silence: it is
printed only after a 200 whose body parsed as a JSON array of objects each
carrying an integer `number`. Anything else — a 404 on a repository this token
cannot see, a 403 rate limit, an unparseable body, a missing field — exits 1.

WHAT IT NEEDS, and what each absence costs:

* a git remote named `origin` whose URL names an owner and a repository, or
  `GITHUB_REPOSITORY` set as `<owner>/<repo>`. Neither is a repository with no
  forge at all, and that is exit 1, not an empty enumeration;
* `GITHUB_TOKEN` or `GH_TOKEN` for a private repository. A public one answers
  unauthenticated, with a 60-per-hour budget that this guard's 1 + 2N requests
  will exhaust inside an hour of repeated runs — and an exhausted budget is a
  403, which is exit 1, which is NOT-RUN. Slower than it should be is better
  than confidently wrong;
* `GITHUB_API_URL` for an enterprise host; the public API otherwise.

It reads the forge and writes nothing to it.
"""

import functools
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

#: Exit codes, named where both this file and its caller can read them.
CANNOT_LOOK = 1
ABSENT = 3

TIMEOUT = 20.0
PAGE = 100
#: A stop on pagination rather than a limit on correctness: a repository with
#: more open pull requests than this is one where the enumeration is wrong to
#: silently truncate, so it exits 1 instead.
PAGES = 20

#: `https://host/owner/repo(.git)`, `git@host:owner/repo(.git)`, `ssh://…`.
REMOTE = re.compile(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$")


class CannotLook(Exception):
    """The observer's problem, never the payload's."""


class Absent(Exception):
    """The payload's, never the observer's: that head really has no such path."""


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return CANNOT_LOOK


@functools.lru_cache(maxsize=1)
def slug() -> str:
    """`<owner>/<repo>` for the current directory's repository."""
    declared = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if declared:
        if declared.count("/") != 1 or not all(declared.split("/")):
            raise CannotLook(f"GITHUB_REPOSITORY={declared!r} is not <owner>/<repo>")
        return declared
    found = subprocess.run(["git", "remote", "get-url", "origin"],
                           capture_output=True, text=True)
    if found.returncode != 0:
        raise CannotLook("this checkout has no remote named origin, so it names no "
                         "forge repository to ask about open pull requests")
    matched = REMOTE.search(found.stdout.strip())
    if matched is None:
        raise CannotLook(f"the origin URL {found.stdout.strip()!r} names no "
                         "<owner>/<repo> this reader can address")
    return f"{matched.group(1)}/{matched.group(2)}"


def get(path: str, raw: bool = False) -> bytes:
    """One API read. Raises `CannotLook` for anything that is not a 200 body.

    A 404 is deliberately NOT special-cased here: on the pull-request endpoints
    it means a repository these credentials cannot see, which is the observer's
    problem. Only the caller reading a payload path knows that a 404 there is an
    absence, and it says so by catching `urllib.error.HTTPError` itself.
    """
    base = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    headers = {"Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "check-sitter-version/0779"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{base}{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:
            return answer.read()
    except urllib.error.HTTPError:
        # Load-bearing: `HTTPError` IS a `URLError`, so without this the clause
        # below would swallow every status into `CannotLook` and `blob` could
        # never tell a 404 absence from a refusal.
        raise
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise CannotLook(f"{path} could not be read: {error}") from error


def readable(path: str) -> bytes:
    """`get`, with every HTTP status that is not 200 turned into `CannotLook`.

    The status alone is reported — never the body, which on some forge errors
    echoes the request, and never the credential, which is a header this file
    must be readable enough to prove it does not print.
    """
    try:
        return get(path)
    except urllib.error.HTTPError as error:
        raise CannotLook(f"{path} answered HTTP {error.code}") from error


def numbers() -> list[int]:
    """Every open pull request's number. Empty only as a positive claim."""
    found: list[int] = []
    for page in range(1, PAGES + 1):
        body = readable(f"/repos/{slug()}/pulls?state=open&per_page={PAGE}&page={page}")
        try:
            listed = json.loads(body)
        except ValueError as error:
            raise CannotLook(f"the open-pull-request list did not parse as JSON: {error}") \
                from error
        if not isinstance(listed, list):
            raise CannotLook("the open-pull-request list answered something that is not a list")
        for item in listed:
            if not isinstance(item, dict) or not isinstance(item.get("number"), int):
                raise CannotLook("an entry in the open-pull-request list carries no "
                                 "integer number, so this enumeration is not one")
            found.append(item["number"])
        if len(listed) < PAGE:
            return found
    raise CannotLook(f"more than {PAGE * PAGES} open pull requests, so this enumeration "
                     "would be truncated rather than complete")


def head(number: int) -> str:
    """One pull request's head commit sha, asked for that pull request alone."""
    body = readable(f"/repos/{slug()}/pulls/{number}")
    try:
        pull = json.loads(body)
    except ValueError as error:
        raise CannotLook(f"pull request {number} did not parse as JSON: {error}") from error
    sha = pull.get("head", {}).get("sha") if isinstance(pull, dict) else None
    if not isinstance(sha, str) or not sha:
        raise CannotLook(f"pull request {number} carries no head sha, so nothing can be "
                         "read at its head")
    return sha


def blob(number: int, path: str) -> bytes:
    """`path` at that pull request's head. `Absent` if the head really lacks it.

    The head sha is resolved here rather than taken from the enumeration's own
    list response: a field missing from a list is the silence this whole
    protocol exists to refuse, and a per-pull-request read can insist on it.
    """
    address = f"/repos/{slug()}/contents/{urllib.parse.quote(path)}?ref={head(number)}"
    try:
        return get(address, raw=True)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise Absent(address) from error
        raise CannotLook(f"{address} answered HTTP {error.code}") from error


def main(argv: list[str]) -> int:
    try:
        if not argv:
            print("\n".join(str(number) for number in numbers()))
        elif len(argv) == 1:
            print(head(int(argv[0])))
        elif len(argv) == 2:
            sys.stdout.buffer.write(blob(int(argv[0]), argv[1]))
        else:
            return fail(f"usage: {sys.argv[0]} [<number> [<path>]]")
    except Absent:
        return ABSENT
    except CannotLook as error:
        return fail(str(error))
    except ValueError as error:
        return fail(f"a pull-request number this reader cannot parse: {error}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
