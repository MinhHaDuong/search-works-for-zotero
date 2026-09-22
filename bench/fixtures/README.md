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
admitted archives are data, in `archives.json` beside this file: one entry
per archive with its hosts, the identifier form, the version rule, and the
admission probe under the five-part test ratified 2026-09-04 — robot-open,
licence-open, reputable, byte-exact identifier, ten years old — recorded as
one real fetch (date, URL, status, content type, first bytes). A new archive
is admitted by adding an entry with its probe, never by editing a set in
`fetch_recipe.py`, which derives everything it checks from that file. The
entries as of 2026-09-06, and the identifier each pins:

| archive | identifier | version |
|---|---|---|
| Internet Archive | item identifier | none; hash pins the bytes |
| Wikimedia Commons | file page | file history; hash pins the version |
| Wikisource | permanent revision id (`oldid`) | the revision is the version |
| Wikipedia | `<lang>:<Title>@<oldid>`, the article namespace fetched as raw wikitext | the revision is the version; an interlanguage link is a `same-subject` relation, never a translation |
| HAL | `hal-…`, `tel-…` | required, `vN`; narrow exception, existing records only (Anubis challenge, pinned once by hand) |
| arXiv | `NNNN.NNNNN` | required, `vN`; the PDF may be regenerated, so a hash mismatch is a text diff to inspect |
| Zenodo | version DOI | required; never the concept DOI |
| FAOLEX | `LEX-FAOC…` | none; admitted for Decision 11/2017 only (allowlist `LEX-FAOC179224`), with the `docs/pdf/` address, hash, and Wayback capture date pinned |
| UK Government Web Archive | dated snapshot URL | the timestamp is the version; the host answers scripts with a WAF refusal, so a snapshot is pinned once by hand |
| Project Gutenberg | numeric ebook identifier | none; each official distribution is hash-pinned because Gutenberg corrects files in place |
| Gallica | `ark:/12148/…` | **dropped** 2026-09-04: every scripted fetch is answered with an ALTCHA challenge (429 on re-probe); a ruled-shape attachment naming it is refused, a legacy-shape record is tolerated until the recipe lane retires it and is never fetched (`dropped-archive`) |

Nothing is deposited anywhere by this project to manufacture an identifier.
`fetch_recipe.py` refuses a recipe that breaks any of this before it fetches a
byte, and `tests/test_fixture_recipe.py` proves the refusal fires on the exact
defects the closed PR shipped and on each of the ruled-shape offences.

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

As of 2026-09-06, the recipe holds 104 records: 103 with the bytes hashed and 1
with an identifier and a stated reason the hash is still open (1 internet-archive). Every record is at the ruled shape of ticket 0721 (topic, stratum, per-attachment
language and charset, relations labelled truthfully); the disposition of the 26
pre-build records is in ticket 0721's log.

Shape against the census of `verification/LIBRARY-CENSUS-0029.md` (attachments
are the unit for formats; records for the rest): 115 attachments, PDF 45
(39,1 %, census 56,9 %), HTML 51 (44,3 %, census 33,0 %),
other formats 19 (16,5 %, census 9,2 %); 29 PDFs past the 100-page
cap (64,4 % of PDFs, census 13,0 %); 13 declared failure controls;
4 record-only items (3,8 %, census 14,8 %); 4 records with a
child note (census 8,2 %); the Zotero language field empty on 40 records and
malformed on 26 (63,5 % together, census about half). Strata:
core 86, reserve 18. Topics: hss 36, economics 28, energy 13, environment 13, development 8, uncertainty 6. Attachment languages: en 37, vi 35, fr 13, zh 8, hi 5, de 5, es 4, ar 4, ru 4. Item types: book 29, statute 18, encyclopediaArticle 15, bookSection 11, journalArticle 8, report 6, webpage 4, preprint 3, dataset 3, thesis 2, map 2, conferencePaper 1, newspaperArticle 1, presentation 1.

| id | topic | stratum | type | language(s) | format(s) | archive(s) | pages | pinned |
|---|---|---|---|---|---|---|---|---|
| bastiat-1862-oeuvres-completes-t1 | economics | reserve | book | fr | txt zip | project-gutenberg | — | sha256 |
| bettencourt-2012-professional-diversity-cities-arxiv | economics | core | preprint | en | pdf tgz | arxiv | 19 | sha256 |
| bettencourt-2014-professional-diversity-cities-scirep | economics | core | journalArticle | en | — (record only) | — | — | n/a |
| bonet-1899-dictionnaire-annamite-francais-t1 | hss | core | book | vi | pdf | internet-archive | 488 | sha256 |
| bonet-1899-dictionnaire-annamite-francais-t2 | hss | core | book | vi | pdf | internet-archive | 552 | sha256 |
| cournot-1838-recherches-ia | economics | core | book | fr | pdf | internet-archive | 230 | sha256 |
| cournot-1897-researches-bacon | economics | core | book | en | pdf | internet-archive | 229 | sha256 |
| dai-viet-su-ky-toan-thu-ngoai-ky-1-zh | hss | core | bookSection | zh | html | wikisource | — | sha256 |
| dai-viet-su-ky-toan-thu-quyen-thu-zh | hss | core | book | zh | html | wikisource | — | sha256 |
| des-michels-1884-kim-van-kieu-t1 | hss | core | book | fr | pdf | internet-archive | 316 | sha256 |
| des-michels-1885-kim-van-kieu-t2 | hss | core | book | fr | pdf | internet-archive | 305 | sha256 |
| dli-1915-arthashastra-hindi | economics | reserve | book | hi | pdf pdf txt | internet-archive | 265 | sha256 |
| doe-2011-quadrennial-technology-review | energy | core | report | en | pdf | osti | 168 | sha256 |
| epa-2016-ghg-inventory-1990-2014 | environment | core | report | en | pdf pdf zip | zenodo | 93 | sha256 |
| gutierrez-2014-diagnostico-ambiental-trevelez | environment | core | report | es | pdf | zenodo | 615 | sha256 |
| ha-duong-1998-irreversibilite-these | uncertainty | core | thesis | fr | pdf | hal | 256 | sha256 |
| ha-duong-2005-modeles-de-precaution-hdr | uncertainty | core | thesis | fr | pdf | hal | 180 | sha256 |
| hal-04332519-economies-of-scale | economics | core | journalArticle | en | pdf | hal | 7 | sha256 |
| hal-04826774-lich-su-sach-nam-ky | hss | core | conferencePaper | vi | pdf | hal | 2 | sha256 |
| ibanez-2015-desarrollo-humano-sustentable | development | core | journalArticle | es | pdf | zenodo | 28 | sha256 |
| ibn-khaldun-1904-muqaddimah | hss | reserve | book | ar | pdf txt | internet-archive | 528 | sha256 |
| jevons-1865-coal-question | energy | core | book | en | pdf | internet-archive | 366 | sha256 |
| jevons-1871-theory-of-political-economy | economics | core | book | en | pdf txt epub | internet-archive | 296 | sha256 |
| johnson-1785-dictionary | hss | reserve | book | en | pdf | internet-archive | 1104 | sha256 |
| karamzin-1818-istoriya-gosudarstva-rossiyskogo-t1-gl1 | hss | reserve | bookSection | ru | html | internet-archive | — | sha256 |
| keynes-1921-application-of-probability-to-conduct | uncertainty | core | bookSection | en | — (record only) | — | — | n/a |
| keynes-1921-treatise-on-probability | uncertainty | core | book | en | pdf | internet-archive | 492 | sha256 |
| korotayev-2015-east-africa-malthusian-trap | development | core | preprint | en | pdf | arxiv | 30 | sha256 |
| macias-2014-crecimiento-desigualdad-pobreza | development | reserve | journalArticle | es | pdf | scielo | 26 | sha256 |
| makarov-2013-climate-change-challenge-world-economy | economics | core | journalArticle | ru | — (record only) | — | — | n/a |
| malynes-1622-lex-mercatoria | economics | reserve | book | en | pdf | internet-archive | 515 | open |
| menger-1871-grundsaetze | economics | reserve | book | de | txt pdf | internet-archive | 307 | sha256 |
| menger-1884-irrthuemer-des-historismus | economics | reserve | book | de | pdf | internet-archive | 106 | sha256 |
| nguyen-du-truyen-kieu-vi-wikisource | hss | core | book | vi | html | wikisource | — | sha256 |
| nhandan-1998-06-21-tin-kinh-te | economics | reserve | newspaperArticle | vi | html | internet-archive | — | sha256 |
| ormos-2014-entropy-asset-pricing | economics | core | journalArticle | en | pdf | europe-pmc | 21 | sha256 |
| ormos-2015-entropy-asset-pricing-arxiv | economics | reserve | preprint | en | — (record only) | — | — | n/a |
| pei-2015-climate-macroeconomic-preindustrial-europe | economics | core | journalArticle | en | pdf | europe-pmc | 17 | sha256 |
| poincare-1912-calcul-des-probabilites | uncertainty | core | book | fr | pdf | internet-archive | 352 | sha256 |
| porte-1770-science-des-negocians | economics | core | book | fr | pdf | internet-archive | 788 | sha256 |
| ramsey-1931-foundations-of-mathematics | uncertainty | reserve | book | en | pdf | internet-archive | 340 | sha256 |
| rethore-2013-wind-farm-optimization | energy | core | presentation | en | pdf | zenodo | 24 | sha256 |
| sanguo-yanyi-ch01-chinapage-1999 | hss | reserve | webpage | zh | html | internet-archive | — | sha256 |
| sanzijing-chinapage-1999 | hss | reserve | webpage | zh | html | internet-archive | — | sha256 |
| satw-2011-erneuerbare-energien | energy | core | report | de | pdf | zenodo | 32 | sha256 |
| schindler-2015-alien-species-health-dataset | environment | core | dataset | en | xlsx | zenodo | — | sha256 |
| smith-1776-wealth-of-nations | economics | core | book | en | txt html epub | project-gutenberg | — | sha256 |
| tolstoy-1910-sueverie-gosudarstva | hss | reserve | book | ru | html | internet-archive | — | sha256 |
| tran-trong-kim-1920-viet-nam-su-luoc-q1 | hss | reserve | book | vi | djvu | wikimedia-commons | 294 | sha256 |
| tran-trong-kim-1920-viet-nam-su-luoc-wikisource | hss | core | book | vi | html | wikisource | — | sha256 |
| tran-trong-kim-1920-viet-nam-su-luoc-wikisource-q1-nuoc-viet-nam | hss | core | bookSection | vi | html | wikisource | — | sha256 |
| tran-trong-kim-1920-viet-nam-su-luoc-wikisource-q1-p1-ch1 | hss | core | bookSection | vi | html | wikisource | — | sha256 |
| tran-trong-kim-1920-viet-nam-su-luoc-wikisource-q1-p1-ch2 | hss | core | bookSection | vi | html | wikisource | — | sha256 |
| tran-trong-kim-1920-viet-nam-su-luoc-wikisource-q1-p1-ch3 | hss | core | bookSection | vi | html | wikisource | — | sha256 |
| tran-trong-kim-1920-viet-nam-su-luoc-wikisource-q1-p1-ch4 | hss | core | bookSection | vi | html | wikisource | — | sha256 |
| tran-trong-kim-1928-viet-nam-su-luoc-q2 | hss | reserve | book | vi | pdf | wikimedia-commons | 347 | sha256 |
| vn-constitution-1992-en | hss | core | statute | en | html | wikisource | — | sha256 |
| vn-constitution-1992-vi | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-i | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-ii | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-iii | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-iv | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-ix | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-v | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-vi | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-vii | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-viii | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-x | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-xi | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-constitution-1992-vi-chuong-xii | hss | core | statute | vi | html | wikisource | — | sha256 |
| vn-decision-11-2017-qdttg-solar-fit-en | energy | core | statute | en | pdf | faolex | 9 | sha256 |
| vn-law-electricity-2004-vi | energy | core | statute | vi | html | wikisource | — | sha256 |
| vn-law-energy-efficiency-2010-vi | energy | core | statute | vi | html | wikisource | — | sha256 |
| vn-law-environment-2005-vi | environment | core | statute | vi | html | wikisource | — | sha256 |
| vnembassy-usa-1999-tinh-hinh-lao-dong | economics | reserve | webpage | vi | html | internet-archive | — | sha256 |
| vuillemin-1875-carte-concessions-nord-pas-de-calais | energy | core | map | fr | jpg | wikimedia-commons | — | sha256 |
| vuillemin-1875-production-pas-de-calais | energy | core | map | fr | jpg | wikimedia-commons | — | sha256 |
| walras-1900-elements | economics | core | book | fr | pdf | internet-archive | 270 | sha256 |
| wb-2016-vietnam-2035-en | development | core | book | en | pdf | world-bank-okr | 409 | sha256 |
| wb-2016-vietnam-2035-en-overview | development | core | bookSection | en | pdf | world-bank-okr | 114 | sha256 |
| wb-2016-vietnam-2035-vi | development | core | book | vi | pdf | world-bank-okr | 584 | sha256 |
| wb-2016-vietnam-2035-vi-overview | development | core | bookSection | vi | pdf | world-bank-okr | 168 | sha256 |
| wittkopf-2016-bipv-methodological-framework | energy | core | journalArticle | en | pdf | zenodo | 24 | sha256 |
| worldbank-2009-vietnam-energy-mitigation | energy | core | report | en | pdf txt | world-bank-okr | 33 | sha256 |
| worldbank-2015-state-trends-carbon-pricing | economics | core | report | en | pdf | world-bank-okr | 92 | sha256 |
| wp-climate-change-ar | environment | core | encyclopediaArticle | ar | html | wikipedia | — | sha256 |
| wp-climate-change-de | environment | core | encyclopediaArticle | de | html | wikipedia | — | sha256 |
| wp-climate-change-en | environment | core | encyclopediaArticle | en | html | wikipedia | — | sha256 |
| wp-climate-change-es | environment | core | encyclopediaArticle | es | html | wikipedia | — | sha256 |
| wp-climate-change-fr | environment | core | encyclopediaArticle | fr | html | wikipedia | — | sha256 |
| wp-climate-change-hi | environment | core | webpage | hi | html | wikipedia | — | sha256 |
| wp-climate-change-ru | environment | core | encyclopediaArticle | ru | html | wikipedia | — | sha256 |
| wp-climate-change-vi | environment | core | encyclopediaArticle | vi | html | wikipedia | — | sha256 |
| wp-climate-change-zh | environment | core | encyclopediaArticle | zh | html | wikipedia | — | sha256 |
| wp-economics-vi | economics | core | encyclopediaArticle | vi | html | wikipedia | — | sha256 |
| wp-inflation-ar | economics | core | encyclopediaArticle | ar | html | wikipedia | — | sha256 |
| wp-inflation-en | economics | core | encyclopediaArticle | en | html | wikipedia | — | sha256 |
| wp-inflation-hi | economics | core | encyclopediaArticle | hi | html | wikipedia | — | sha256 |
| wp-inflation-ru | economics | core | encyclopediaArticle | ru | html | wikipedia | — | sha256 |
| wp-inflation-zh | economics | core | encyclopediaArticle | zh | html | wikipedia | — | sha256 |
| wp-sustainable-development-vi | development | core | encyclopediaArticle | vi | html | wikipedia | — | sha256 |
| yan-fu-1902-yuanfu-yishi-liyan | economics | core | bookSection | zh | html wikitext | wikisource | — | sha256 |
| zenodo-11353-open-data-energy-india | energy | core | dataset | en | xlsx | zenodo | — | sha256 |
| zenodo-1246601-green-economy-employment | energy | core | dataset | en | xlsx docx | zenodo | — | sha256 |

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
`txt`, `html`, `md`, `epub`, `docx`, `xlsx`, `odt`, `rtf`, `jpg`, `png`,
`zip`, `tgz`; default `pdf` — the office, image and archive formats are the
9,2 % of files the extractor never reads and are failure controls by
construction), `min_size` (bytes below which a download is treated as an
error page; default 1 000), `archive_checksums` (the archive's own md5 or
sha1 where it publishes one), `page_count`, `provenance_check`,
`wayback_capture` (for the unversioned database of record).

### The ruled shape (ticket 0721)

A record in the `attachments` shape carries, beyond the parent fields above
(`item_type`, `type_fidelity`, `work_id`, `work_relations`,
`structural_features`):

- `topic`, one of the author's library's seven: `economics`, `uncertainty`,
  `energy`, `environment`, `development`, `sts`, `hss`; a record kept
  off-topic says why in `retained_reason`;
- `stratum`, `core` (representative, following the census marginals) or
  `reserve` (adversarial); a reserve member names the mechanism ids it
  carries in `mechanisms` (a list of strings, empty for core);
- `language_field`, the exact string written to Zotero's language field —
  `""` or a malformed spelling on purpose, following the census — while the
  recipe's `language` stays the declared language of the work and is the
  fallback when no `language_field` is given;
- `citation`, any subset of `{doi, isbn, url}`, written to the Zotero fields
  the item type has (`zotero-item-fields.json`, Zotero's public schema reduced
  to item type → field names; `golden_fixture.py item-fields` regenerates it)
  and to Extra as `DOI: …` / `ISBN: …` / `URL: …` otherwise;
- `notes`, an optional list of `{id, html}` child notes, `id` a globally
  unique slug;
- `record_only: true` with `attachments: []` for a record with no file
  (14,8 % of the census); an empty attachment list without the flag is an
  offence, and so is the flag with attachments;
- `work_relations[].type` gains `same-subject`, a Wikipedia interlanguage
  link, never recorded as `translation`.

Each attachment carries, beyond the existing fields (`language`, `role`,
`relation`, `selection_expectation`, `cap_expectations`, provenance):

- `charset`, required for every text format (`html`, `wikitext`, `txt`,
  `md`) and a codec Python can name: `utf-8`, or the authentic legacy charset
  the archive served (`windows-1258`, `koi8-r`, `windows-1251`, `gb2312`,
  `big5`, `iso-8859-1`, `windows-1256`, …). The injection writes it on the
  Zotero attachment item, canonicalised as Zotero stores it (`iso-8859-1`
  becomes `windows-1252`, `gb2312` becomes `gbk`), and on the upload's
  `Content-Type`; `fetch_recipe.py` checks a text download decodes under it.
  No file is ever converted. A legacy-shape record (no `attachments`) carries
  no charset until the recipe lane rewrites it;
- `content_type_declared`, optional, the MIME type written instead of the
  format's own — the lying-MIME failure control only;
- `min_body_chars`, optional (default 2 000): the injection refuses a text
  attachment whose decoded body — HTML tags stripped, wikitext templates,
  comments and category links stripped — is shorter, unless the attachment
  declares a `failure_control`. This is the transclusion-skeleton guard: two
  of ticket 0632's three Wikisource records were work pages carrying only
  header templates;
- `encoding_note`, optional prose on a legacy encoding.

Optional, and checked by the validator when present: `failure_control`, the
declaration the 2026-09-03 ruling requires of every failure control — an
object with exactly `expected_state` (`unindexed`, Zotero's own name for an
attachment it finished trying and left without full text),
`expected_degradation` (why, in words a reader can check against the bytes),
and `answer_set_participation` (`none`: a control is never a pinned answer).
Three records carry it (author's rulings of 2026-09-04 and 2026-09-06): the
Trần Trọng Kim DjVu, which Zotero's extraction dispatch never processes, and
the two un-OCR'd scans, Trần Trọng Kim volume II and Ramsey 1931, which yield
no text. A control is also exempt from the body-text floor above.

## The pinned subset and the export

`recipe-pinned.json` is derived data, not a second recipe: `select_hashed.py`
writes it from `recipe.json` as the records whose every attachment carries a
sha256, in the parent's order, and a test holds it byte-identical to that
output. It is the one file `golden_fixture.py inject`, `golden_fixture.py
export` and the offline replay all read, so the export manifest's
`recipe_sha256` pins exactly the content the replay re-derives. Regenerate it
whenever `recipe.json` gains a pinned hash, and re-export.

The export (`golden_fixture.py export`, destination `export/`) is a raw
capture of the live API: `items.json` (parents, attachments and child notes),
one `fulltext/<key>.json` per indexed attachment, and `manifest.json`
(`schema_version` 2) binding each parent to its Zotero key, its note keys and
its `record_only` flag under `parents`, and each attachment row to its recipe
record under `attachments`. It also counts `note_count`,
`record_only_count`, `strata`, `topic_counts`, `format_counts` (by content
type) and `language_counts` (per attachment's declared language). The loader
in `make_index_fixture.mjs` reads schema 2 only and refuses the schema-1
export of 2026-09-06 with a message naming the re-export: that export lacked
explicit charsets, the observed reindex mode and the parent bindings, and is
superseded by the re-export this schema exists for. A declared failure
control is exported with `terminal_state`
`unindexed`, no fulltext file, its declaration copied from the recipe and the
state the reindex observed. It is accepted on evidence from the run itself:
the reindex must have watched Zotero go idle and leave the attachment at the
declared state, and Zotero must hold no text for it — either no `/fulltext`
census row (a DjVu, never dispatched) or the empty, missing-marked row at
version 0 that Zotero's `recordMissingContent` writes for a PDF with no text,
with the fulltext route answering 404. Mere absence from the census is
refused, because absence also describes text that was indexed once and
vanished. The replay answers for a control as Zotero did: the census entry
at 0 when Zotero kept one, 404 on its fulltext route, the item itself still
served.
An indexed attachment is refused when the reindex left its fulltext version
unchanged, since Zotero resets that version on every local extraction and an
unchanged one means the client held the item but never read the file.

### Reindex modes, and what the manifest observes

`inject` and `export` take `--reindex-mode stock|uncapped`, `stock` by
default. Stock asks the control plugin for `complete: false`, so Zotero
applies its own `fulltext.pdfMaxPages` and `fulltext.textMaxLength` exactly as
it would to its own extraction; uncapped asks for `complete: true` and both
limits are ignored (plugin 0.2.0 and later; an older plugin, which always
ignored the limits, is refused because it does not echo the mode). The
manifest's `reindex.mode` is recorded as the plugin's status reports it after
the reindex settled, never as typed, and the export refuses when the two
disagree. The two preferences under `zotero` are likewise read live from the
plugin's status (`prefs`), with `--pdf-max-pages` and `--text-max-length`
kept only as optional cross-checks that refuse on mismatch; `plugin_version`
is recorded beside them. In stock mode the export refuses itself when a
captured counter contradicts the recorded preference — an attachment indexed
past the cap, or over the cap and not cut exactly at it — and the loader
applies the same rule to a manifest claiming stock. The binding record stays
each row's observed `indexed_pages`/`total_pages` and
`indexed_chars`/`total_chars`. `known_defects` lists what the export knows is
wrong with the fixture as injected — declared by the operator with
`--known-defect`, or detected by the export itself (a text attachment
indexed one character per byte although its item declares its charset) —
and records them without repairing anything, because the export is what
Zotero holds. A charset the injection set explicitly is no longer a defect;
a charset Zotero holds that differs from the recipe's is metadata drift, and
the export refuses.

### Notes, record-only parents, and retiring a record

Child notes are written as Zotero note items under the managed marker
`zoteus-golden-note:<id>`, reconciled idempotently like attachments (a
changed `html` is an update, never a second note), exported in `items.json`
and served by the replay on `/items/<parent>/children`. A record-only parent
is injected with no attachment and takes no part in the reindex. `retire
--ids a,b` moves managed parents out of the fixture collection by rewriting
their `collections` field — children follow, nothing is deleted or trashed —
so a later `inject` no longer sees them as stale; a parent already outside the
collection is reported as absent, and a second run changes nothing.

A third row shape, `indexed-not-served`, records a fact of the local API
found on the first real run: `/items/<key>/fulltext` answers 404 for every
content type outside `Zotero.Fulltext.isCachedMIMEType` (PDF, HTML, EPUB), so
a plain-text attachment Zotero has indexed — the three Wikisource `wikitext`
records, in the census with their character counts — has no body to fetch,
and the product indexes it from metadata only. The export accepts such a row
only for an unserved content type with the reindex's own `indexed`
observation; the same 404 on a PDF is vanished text and stays refused. The
replay lists it in the census and answers 404 on its route, as Zotero does.

## The question bank and the golden gate

`questions/` is the fourth layer, the Menagerie question bank (schema
`menagerie-bank/v2`, ticket 0722): one JSON file per question pinning rows of
the export by attachment key, quoted span and printed page, with the citation
chain a complete reply carries. `questions/README.md` documents the record,
the closed vocabularies, the replies schema the runner writes and the report
the scorer produces; `questions/bank.schema.json` is the same record as a JSON
Schema. `make golden` validates the bank against `export/` (every quote located
and its offset stamped) and scores `bench/results/golden/replies.json`;
`make golden-run` produces that file from a built `fork/` over the replay.

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

## Import into your own Zotero (RIS package)

Ticket 0721. Beside `items.json`, `fulltext/` and `manifest.json`, which the
harness replays and no person can hand to Zotero, `export/menagerie.ris` is the
Menagerie as a colleague imports it in one gesture: one RIS record per recipe
parent, with its metadata, its managed tag, its Extra lines, its child notes,
and one `L1` file link per attachment whose bytes the recipe has pinned, as a
path relative to the RIS file (`attachments/<attachment id>.<ext>`). The RIS is
derived data and committed, like `recipe-pinned.json`: `make menagerie-ris`
writes it from `recipe.json` and `export/` (the export supplies each parent's
Zotero key, as `ID`, and the record order), and `tests/test_export_ris.py` holds
the committed file byte-identical to that output, so a recipe or export change
without a regeneration is red. The output carries no timestamp.

The bytes are never committed (Malynes alone is 352 MB). They are assembled
locally:

```bash
make menagerie-ris                                        # export/menagerie.ris
make menagerie-package MENAGERIE_PACKAGE=/path/menagerie.zip
```

The package is a zip holding `menagerie.ris` at its root, `IMPORT.txt`, and
`attachments/<id>.<ext>` for every pinned attachment of a parent that is not
`record_only`. Each file is taken from the recipe's verified fetch cache
(`MENAGERIE_CACHE`, default `~/data/golden-fixture-cache`, the same directory
`fetch_recipe.py --cache-dir` fills) only after its sha256 matches the recipe;
a mismatch, a missing file or a symlink refuses the whole package and leaves
nothing behind. Nothing is read from Zotero's storage. An unpinned record
(`sha256: null`) gets a record and no `L1`; a `record_only` parent gets a
record and no file.

**The gesture**, for the colleague. Unzip the archive, keeping `menagerie.ris`
and `attachments/` side by side. In Zotero: File → Import… → "A file (BibTeX,
RIS, Zotero RDF, etc.)" → choose `menagerie.ris`. Leave "Place imported
collections and items into new collection" checked: the items land in a
collection named after the file, `menagerie`. Under file handling, "Copy files
to the Zotero storage folder" (the default) makes the library self-contained;
"Link to files in original location" keeps them where they were unpacked, as
linked files. Finish. Each `L1` becomes a child attachment of its parent.

Why this works, read off Zotero's own code in the import direction
(zotero/translators `RIS.js`, lastUpdated 2026-01-05; zotero/zotero
`translate_item.js`, `fileInterface.js`, `translate_firefox.js`): `L1` maps to
`attachments/PDF` (RIS.js `fieldMap`), the path is handed to the item saver,
which resolves it as a URI against the RIS file first and as a path under the
file's directory second (`_parsePathURI`, `_parseRelativePath`), then copies
it (`Zotero.Attachments.importFromFile`) or, with the link option, links it
(`linkFromFile`); the content type is sniffed from the file, so `L1` serves
every format, and the attachment's title is the file name without its
extension. `TY` is read through `importTypeMap`, `AU` without a comma becomes a
single-field creator (`fieldMode = 1`), `LA` maps to `language`, `M2` to
`extra` with repeated lines joined by newlines, `N1` to one child note per
line (a value carrying HTML is stored as-is), `KW` to a tag, `DO` to `DOI`,
`UR` to `url`, `DB` to `archive`, `AN` to `archiveLocation`, and `ID` is
`__ignore`. The file is UTF-8 with a BOM and CRLF line endings, which the
reader locks its charset on. The complete argument, mapping by mapping, is the
module docstring of `export_ris.py`.

**What RIS cannot express, and Zotero RDF would.** The RIS is a lossy view of
the fixture, and the import will differ from the group library on these points:

- *Item types without a TY.* `document` has no RIS type; it exports as `GEN`,
  which imports as `journalArticle`. Every record of the 2026-09-06 recipe is a
  legacy-shape `document`, so every one of the 26 imports as a journal article;
  `make menagerie-ris` logs the count. `preprint` and `standard` fall to `GEN`
  the same way. A ruled-shape record with a type of its own (`book`, `report`,
  `thesis`, …) round-trips.
- *Notes.* A note's HTML is folded to one line; its managed marker
  (`zoteus-golden-note:<id>`) and its Zotero key are not carried, since RIS has
  no tag on a child; and RIS.js drops an `N1` equal to the parent's title.
- *Work relations.* Carried only as the text of the Extra line
  `ticket-0029 work relations: […]`, which is also where the fixture keeps them;
  RDF would carry Zotero's related-item links, of which the fixture has none.
- *An empty language field.* RIS.js drops an empty value before mapping it, so
  no `LA` is written and the import leaves the field empty, as the fixture has
  it, by omission rather than by assertion. A malformed value on purpose
  (`Français`, `en-US`) is carried verbatim.
- *A creator with a comma.* RIS.js splits `AU` on the first comma into last and
  first name; the fixture holds every author as one single-field name. The
  value is emitted as given and the script warns; three records of the current
  recipe are affected (the Einstein–Minkowski volume, the two des Michels
  editions, whose names carry `translated by …` and `(ed., transl.)`).
- *Tags.* Only the parent's `zoteus-golden-source:<id>` marker travels; the
  attachment markers (`zoteus-golden-attachment:<id>`) do not.
- *Collections.* RIS has no collection. Zotero puts everything in a new
  collection named after the file, not in the fixture's collection `3AY48MA5`.
- *Attachment metadata.* Title (becomes the file name minus its extension),
  charset and content type (sniffed; the three `text/plain` wikitext files are
  exactly where the fixture's Zotero guessed `windows-1252`), link mode (the
  fixture's is `imported_file`), the recipe's `content_type_declared` lie, and
  the attachment's Zotero key.
- *Zotero keys.* `ID` carries the parent's key for a reader; the import mints
  new keys. `manifest.json` stays the binding of keys to recipe records.
- *An ISBN on a type whose `SN` means something else.* On a journal, magazine
  or newspaper article `SN` imports as ISSN, on a report as report number, so
  such an ISBN goes to Extra as `ISBN: …`, which is also what the fixture
  writes to Zotero for a type without the field.

**Checking an import** on a client, once the zip is unpacked beside nothing
else: the new collection `menagerie` holds 26 items, all of type Journal
Article (the current recipe), 17 of them with one child attachment and 9 with
none (the 4 HAL, 4 Gallica and Malynes records, unpinned); every attachment
opens, the 13 PDFs, the DjVu (`tran-trong-kim-1920-viet-nam-su-luoc-q1`) and
the 3 wikitext files as text; each parent carries the tag
`zoteus-golden-source:<id>`, an Extra field of four `ticket-0029` lines, the
`archive` and `Loc. in Archive` fields, a URL, and a language except where the
recipe's is empty; with "Link to files in original location", every
attachment's path points into the unpacked `attachments/` directory and
nothing was copied into Zotero's storage.
