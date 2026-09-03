# bench/fixtures/

Two unrelated fixtures share this directory, and they answer different questions.
`make_index_fixture.mjs` writes a tiny SEARCH INDEX of a named schema generation, so the
guard in `bench/index_schema.mjs` can be seen to fire in both directions (ticket 0101):

```bash
node bench/fixtures/make_index_fixture.mjs --both /tmp/fx     # both generations, ~0,2 s
```

600 synthetic passages, deterministic, about 250 KB each, written to a path you name —
`bench/*.sqlite` is git-ignored, and the standing test writes them to a pytest tmpdir. The
`current` fixture is upstream's `createSchema()` DDL verbatim; `prerename` is transcribed
from an index the pre-split fork generation actually built. `tests/test_index_schema_fixtures.py`
drives every real-index bench driver against both.

The rest of this file is about something else entirely.

# The golden fixture corpus — source recipe

Ticket 0029. This directory holds the first of the fixture's three layers, the
**source recipe**: `recipe.json`, one record per document naming the public
archive it comes from, its persistent identifier, the address of the bytes, and
their sha256; and `fetch_recipe.py`, which fetches those bytes into a
git-ignored cache and reports, per document, whether the archive still serves
what the recipe pinned. The other two layers are separate work: an injection
script that puts the documents into a collection of a public Zotero library as
linked-file attachments, and the committed export of what Zotero's own client
extracted from them, which the harness replays through a mock local API. The
rulings that fixed this shape are in `DECISIONS.md`, 2026-09-02, "The golden
fixture corpus".

## Why the fixture is not committed text

zoteus indexes what Zotero's `/fulltext` endpoint serves and never extracts a
PDF for indexing itself. That endpoint serves the desktop client's own
extraction, which stops at 100 pages and 500 000 characters by default and
carries no page breaks. A one-off probe on three documents of the closed
PR #151, recorded with its numbers in the ledger entry named above and not in
`bench/results/`, found the client's text and `pdftotext`'s text of the same
scan sharing between two fifths and three fifths of their vocabulary. A
fixture built from `pdftotext` therefore measures an extractor the system does
not use. The recipe records where the bytes are; the
export records what Zotero made of them; only the second is what the gate
reads.

## Where a document may come from

A document names a public, third-party-hosted, persistent identifier that
resolves to one fixed set of bytes. A personal Zotero library is not one, a
personal homepage is not one, and a publisher's live page is not one. The
admitted archives, and the identifier each pins:

| archive | identifier | version |
|---|---|---|
| Internet Archive | item identifier | none; hash pins the bytes |
| Gallica | `ark:/12148/…` | none; hash pins the bytes |
| Wikimedia Commons | file page | file history; hash pins the version |
| Wikisource | permanent revision id (`oldid`) | the revision is the version |
| HAL | `hal-…`, `tel-…` | required, `vN` |
| arXiv | `NNNN.NNNNN` | required, `vN`; the PDF may be regenerated, so a hash mismatch is a text diff to inspect |
| Zenodo | version DOI | required; never the concept DOI |
| FAOLEX | `LEX-FAOC…` | none; admitted for Decision 11/2017 only, with the `docs/pdf/` address, hash, and Wayback capture date pinned |
| UK Government Web Archive | dated snapshot URL | the timestamp is the version |

Nothing is deposited anywhere by this project to manufacture an identifier.
`fetch_recipe.py` refuses a recipe that breaks any of this before it fetches a
byte, and `tests/test_fixture_recipe.py` proves the refusal fires on the exact
defects the closed PR shipped.

## Licensing bases

Every document is free to redistribute on one of four bases, and its record
says which in `license_basis`:

- **Age.** Published before 1931, the 2026 US bright line, or clear under
  life+70 from the author's death.
- **Statutory exclusion.** Vietnam's Law on Intellectual Property, Article
  15.2, excludes legal normative documents and their official translations
  from copyright, with no age condition.
- **Open licence.** An explicit grant by the rightsholder, such as the Open
  Government Licence on Crown material, or a Creative Commons licence
  declared on a HAL deposit.
- **Author-owned.** The author's own work, authorized by him directly.

A scan's container can carry a copyright the underlying text does not. The
reprint-provenance check reads each file's embedded metadata and front matter
for a modern publisher, date, or "reprint" wording, and the record's
`provenance_check` field says what was found. This check removed Soddy 1926
from the first assembly (a 1983 Allen & Unwin reissue) and swapped the first
Johnson's Dictionary candidate (a scrambled text layer) for a clean 1785
printing. An IPCC report was considered and rejected: the IPCC permits short
excerpts, not whole reports.

## What the recipe holds

Twenty-six records on 2026-09-03: 17 with the bytes hashed, 9 with an
identifier and a stated reason the hash is still open. Three archives answer
scripted clients with a challenge page instead of the file: HAL (Anubis
proof-of-work), Gallica (ALTCHA), and the UK Government Web Archive (a WAF
captcha). Their entries are fetched once in a browser, hashed, and pinned by
hand; `fetch_recipe.py` reports them as `unfetched` until then.

| id | language | tier | facet | archive | pages | bytes pinned |
|---|---|---|---|---|---|---|
| cournot-1838-recherches | fr | MUST | core | gallica | 228 | not yet |
| walras-1900-elements | fr | MUST | core | internet-archive | 270 | sha256 |
| porte-1770-science-des-negocians | fr | MUST | core | internet-archive | 788 | sha256 |
| minkowski-1896-geometrie-der-zahlen | de | SHOULD | core | internet-archive | 274 | sha256 |
| malynes-1622-lex-mercatoria | en | MUST | deep-body | internet-archive | 515 | archive md5/sha1 |
| ramsey-1931-foundations-of-mathematics | en | MUST | core | internet-archive | 340 | sha256 |
| depitre-1908-oeuvres-cournot | fr | MUST | core | gallica | — | not yet |
| ha-duong-2005-modeles-de-precaution-hdr | fr | MUST | core | hal | 180 | not yet |
| ha-duong-1998-irreversibilite-these | fr | MUST | deep-body | hal | — | not yet |
| johnson-1785-dictionary | en | MUST | deep-body | internet-archive | 1 104 | sha256 |
| baudelaire-1857-fleurs-du-mal | fr | MUST | core | internet-archive | 262 | sha256 |
| stein-1925-making-of-americans | en | MUST | deep-body | internet-archive | 940 | sha256 |
| curie-1904-recherches-substances-radioactives | fr | MUST | core | internet-archive | 176 | sha256 |
| einstein-minkowski-1920-principle-of-relativity | en | MUST | core | internet-archive | 260 | sha256 |
| tran-trong-kim-1920-viet-nam-su-luoc-q1 | vi | MUST | core | wikimedia-commons | 294 | sha256 |
| tran-trong-kim-1928-viet-nam-su-luoc-q2 | vi | MUST | deep-body | wikimedia-commons | 347 | sha256 |
| tran-trong-kim-1920-viet-nam-su-luoc-wikisource | vi | MUST | core | wikisource | — | sha256 |
| vn-constitution-1992-vi | vi | MUST | core | wikisource | — | sha256 |
| vn-constitution-1992-en | en | MUST | core | wikisource | — | sha256 |
| hal-04332519-economies-of-scale | vi | MUST | core | hal | — | not yet |
| hal-04826774-lich-su-sach-nam-ky | vi | MUST | core | hal | — | not yet |
| des-michels-1883-luc-van-tien | vi | MUST | core | gallica | 454 | not yet |
| des-michels-1884-kim-van-kieu-t2p1 | vi | MUST | core | gallica | 309 | not yet |
| bonet-1899-dictionnaire-annamite-francais-t1 | vi | MUST | core | internet-archive | 488 | sha256 |
| bonet-1899-dictionnaire-annamite-francais-t2 | vi | MUST | core | internet-archive | 552 | sha256 |
| vn-decision-11-2017-qdttg-solar-fit-en | en | MUST | core | faolex | 9 | sha256 |

## Dropped from the closed PR #151, and why

- **Neurath 1919, Durch die Kriegswirtschaft zur Naturalwirtschaft.** Public
  domain, but no copy in any admitted archive: Internet Archive has none,
  German Wikisource cites it and links only to HathiTrust, Google Books and
  econbiz. Returns when an admitted archive holds it.
- **The UK Highway Code.** Live gov.uk pages are a publisher, not an archive,
  and the UK Government Web Archive answered every request with a captcha, so
  no snapshot timestamp could be confirmed. Returns with a dated snapshot URL
  pinned by hand.
- **Circulars 25/2016/TT-BCT, 41/2010/TT-BTNMT, 42/2010/TT-BTNMT.** Sourced
  from the author's library, which is not a provenance. Vietnamese Wikisource
  holds no ministerial circular as text, only Official Gazette scans that list
  them, so no sibling replaced them; the Vietnamese administrative register is
  the 1992 constitution.
- **Decision 11/2017, Vietnamese original.** The author's library copy is not
  a provenance, and whether FAOLEX holds the Vietnamese text beside the English
  translation could not be read, its record page being closed to scripts. The
  English translation is in.
- **HAL-04214661, Ô nhiễm không khí.** The HAL deposit authorises distribution
  through HAL but carries no reusable licence, and the fixture has no consent
  from its authors. Dropped by the author's 2026-09-03 ruling rather than left
  as an unfetched candidate.
- **The Malynes excerpt and the Ramsey "Electronic Edition".** Private scans;
  both replaced by the full first editions on the Internet Archive.

## Licence flags carried inside the recipe

One entry rests on a basis weaker than the rest and says so in its record: the
Einstein–Minkowski volume is the 1920 University of Calcutta translation by
Saha and Bose, public domain in the United States by its date and under life+70
only from 2045, since Bose died in 1974.

## Fields of a recipe record

Required, and checked by the validator: `id` (slug), `title`, `author`,
`year`, `language` (BCP-47 primary tag), `tier` (`MUST` or `SHOULD`, per R7's
language ruling), `facet` (`core`, `notes`, `group`, `deep-body`), `archive`
(one of the admitted names; FAOLEX only for `LEX-FAOC179224`), `identifier`,
`version` (`vN`, required for HAL, arXiv, Zenodo), `bytes_url` (its host must
belong to the declared archive and to no refused host), `sha256` (or `null`
with `sha256_reason`), `license_basis`.

Recommended, by convention: `bytes_format` (`pdf`, `djvu`, `wikitext`,
`html`; default `pdf`), `min_size` (bytes below which a download is treated as
an error page; default 1 000), `archive_checksums` (the archive's own md5 or
sha1 where it publishes one), `page_count`, `provenance_check`,
`wayback_capture` (for the unversioned database of record), `notes`.

## Re-pinning

Run `python3 bench/fixtures/fetch_recipe.py`. Every document reports one of
five statuses: `match`, `MISMATCH` (with the pinned hash), `unpinned` (the
recipe carries no hash yet), `blocked` (the archive answered a scripted client
with a challenge page or a 401/403/405/429, so the bytes are fetched once in a
browser and pinned by hand), or `unfetched` (a network error or a server
failure, worth a retry). The exit status is 1 when any document is `MISMATCH`
or `unfetched`, 0 otherwise; `blocked` and `unpinned` are expected states, not
failures of the run. A mismatch is inspected, never overwritten: diff the
old and new bytes or their text, decide whether the archive corrected or
replaced the file, and if the new bytes are the ones the corpus should carry,
commit the new hash. That commit's diff is the review artifact, the same rule
D11 applies to the pinned answer sets.
