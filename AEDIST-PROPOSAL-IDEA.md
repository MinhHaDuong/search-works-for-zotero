# AEDIST — Evidence storage for the Energy Transition Monitoring system

**Proposal idea, 2026-09-09.** The storage layer for AEDIST's Energy Transition
Monitoring system, as clarified by the author.
ANR is a possible funding route; the note is to be assessed against a specific
call later. No instrument, eligibility, consortium, budget or submission date
is settled. This is a research concept, not a funding application or a change
to the system requirements owned by [SPEC.md](SPEC.md).

## Proposition

Develop and evaluate the document-evidence storage layer for AEDIST's Energy
Transition Monitoring system. It should make the source material used by the
monitoring system available as identifiable, versioned and locatable evidence,
with text representations suitable for both researchers and automated tools.
The research scope is this layer and its interfaces, not the whole monitoring
system and not an independent Zotero product programme.

The proposed shared text foundation for Zotero AI tools supplies reusable
machinery: native document preparation, structured-text access and selectable
chunk streams. Adapting independent MCP tools and setting up and running the
Challenge are part of the proposed work. They test whether this machinery
supports reliable evidence access beyond one application or retrieval engine.

The Energy Transition Monitoring system is the motivating application. The
Multilingual Menagerie and a domain-specific evaluation arm would let us test
both general document pathologies and the monitoring system's actual evidence
needs. The plugins implement part of the layer; the corpus, evaluation protocol,
Challenge operation and scientific analysis are also substantive outputs.

## Storage boundary to establish

The initial working interpretation is a document-evidence layer: source
documents and bibliographic identity; extraction versions; structured blocks
and page locations; derived chunks; and lineage from each derived object back
to the source version. Fulltext, Structured-text and Chunks stream are read
views over that material, not a complete storage architecture by themselves.

The relation to AEDIST's existing storage remains to be inventoried. In
particular, determine which component retains source bytes and historical
versions, which representations are durable or regenerable, and how changes
invalidate derived state. Zotero's current caches alone must not be assumed to
provide immutable historical evidence. Storage ownership, retention and access
control require design against the monitoring system's needs.

Extracted claims, entities, indicators and time series may consume this layer,
but their schemas and analytical processing are not silently included in it.
Define the boundary with those parts of the system before costing the proposal.
No new choice of database, vector store or graph store is made by this note.

## Scientific problem

An apparently successful search can conceal incomplete extraction, missing
attachments, stale representations or a relevant passage cut away by the
chunking policy. These errors can be mistaken for weaknesses in an embedding
model. Languages and document structures interact with each stage, while
page-level source references can be lost between extraction and presentation.

The proposed research asks: **how can an evolving multilingual document corpus
serve as reproducible, traceable evidence for energy-transition monitoring,
despite extraction errors, changing sources and heterogeneous consumers?**

A candidate monitoring scenario is a researcher revisiting an earlier answer
after its source report has been revised or re-extracted. Can the system
identify the evidence originally used, locate it in the correct source version,
and distinguish changed evidence from changed processing? This is an experiment
to design, not a capability already established for AEDIST.

The contribution must go beyond organising a benchmark or packaging existing
code. It should produce a defensible error model, methods for maintaining
source-grounded representations, and empirical findings about the conditions
under which those methods improve retrieval. Novelty against existing document
processing, information retrieval and RAG research remains to be established.

## Hypotheses to refine and test

- **Shared source representations improve reproducibility.** A versioned text
  interface carrying source identity, locations and freshness can reduce
  unexplained differences between tools and make failures easier to attribute.
  Compare native integrations with adapters to the shared interface while
  holding the retrieval configuration fixed where feasible.
- **Chunking effects depend on the document and language.** No strategy is
  presumed universally best. Compare page, paragraph, section and budget-based
  strategies, including the pinned Zotero chunker where applicable, with
  questions stratified by language, document structure and answer location.
- **Readiness is a research outcome distinct from warm-query speed.** Measure
  how preparation and scheduling affect time to useful results and coverage
  during indexing, including source changes and failures. Test rather than
  assume that independent preparation or incremental consumption helps.
- **Versioned evidence supports longitudinal monitoring.** Compare how systems
  handle source revisions, extraction changes and regenerated chunks when
  reproducing earlier evidence-based answers. Separate source evolution from
  processing-induced changes; identifying either does not by itself establish
  the correctness of an extracted energy indicator.
- **Visible provenance and incomplete coverage support better judgement.**
  Evaluate citation verification and users' interpretation of incomplete
  results. Retrieval scores alone cannot establish this; it needs a separate
  researcher-facing study with appropriate ethics and data arrangements.

These are candidate hypotheses, not established findings or newly ratified
performance requirements. The protocol must allow null and adverse results.

## Connected work programme

### Shared document access

First inventory AEDIST's current source storage, identifiers, update paths and
downstream consumers. Define the evidence objects and lifecycle needed by the
monitoring system, then map reusable workshop components onto that boundary.

Use the sitter to prepare native structured-text packs and extend the existing
full-text API plugin to expose Fulltext, Structured-text and Chunks stream
views, with a caller-selected chunking strategy. Preserve source locations and
extraction/strategy identity across bounded reads. Keep representation access
separate from embedding, indexing and ranking so independent tools can reuse it.

The initial interface vision is [ticket 0758](tickets/0758-fulltext-api-initial-vision-text-structu.erg);
[ticket 0726](tickets/0726-structured-text-plugin-contract-what-the.erg) owns the
contract work. Their unresolved choices remain unresolved here. Separate
plugin versions and release readiness permit a tested pair without requiring
simultaneous releases. A future native Zotero interface should be able to
replace the plugins without forcing consumers to redesign their pipelines.

### Adapt independent MCP tools

Adapt leading Zotero-facing MCP servers and other suitable retrieval tools to
consume the interface. Select participants using documented criteria such as
active maintenance, practical usage, architectural diversity and willingness
to participate; do not label a tool "leading" without evidence.

Zoteus is an available first integration vehicle, with existing consumer work
in [ticket 0572](tickets/0572-read-structured-text-from-the-sdt-plugin.erg).
Additional tools are candidates, not committed partners. The work concerns
document-consuming integrations rather than changes to general MCP SDKs.
Keep adapters thin and upstreamable, with maintainers' agreement for any
contribution. Compare each tool before and after adaptation, and report the
integration effort as well as retrieval outcomes.

### Set up and run the Challenge

Turn the Multilingual Menagerie and bench into a reproducible public
evaluation exercise, including an energy-transition monitoring arm derived
from representative tasks and source documents. Candidate sources include
research articles, institutional reports and policy documents; their actual
selection, languages and licensing must follow AEDIST's use cases, not an
invented corpus specification. Establish provenance and redistribution conditions,
question and answer annotation procedures, participation instructions, a
submission format, baseline runs and a documented scoring protocol. Recruit
independent participants, support installation, execute or reproduce
submissions, and publish results with explanatory error analyses.

Challenge operation is a deliverable in its own right, not merely publication
of a fixture or leaderboard. Protocol development should address held-out
evaluation, answer leakage, adjudication, participant feedback and corrections.
Keep tuning data distinguishable from evaluation data. The project team should
not be the sole judge of its own implementation without an independently
reviewed protocol and an explicit account of that conflict.

### Explain the results and transfer the methods

Study failure propagation from source availability through extraction,
segmentation, embedding and ranking to the returned citation. Publish
reproducible comparisons, negative results and methods that other scholarly
systems can use. Carry findings into interface revisions and practical
guidance, while retaining pinned versions for comparable Challenge results.

## Evaluation principles

Use cross-tool comparisons and controlled within-tool experiments. Where
possible, hold corpus, questions, model, precision, token budget and hardware
constant when changing the text source or chunking strategy. Where that is
impossible, report the confound explicitly. A common interface does not itself
make different retrieval systems scientifically comparable.

Measure retrieval quality, citation/location correctness, source coverage and
freshness, readiness during builds, resource use, and recovery from unavailable
or changed inputs. Include reproduction of past evidence states and the
traceability of downstream outputs to source versions. Disaggregate results by language and document class rather
than relying only on an overall average. Record CPU/GPU execution and model
identity, and distinguish extraction cost from embedding and query cost.
Determine sample sizes, uncertainty estimation and any acceptance criteria in
the later protocol; this note sets no numerical targets.

Use licensed public fixtures for reproducible runs. Real research libraries
may support supplementary studies with consent and controlled access, but
must not become an undocumented prerequisite for reproducing the main result.
Separate what an automated score establishes from what needs human judgement.

## Outputs and prospective collaboration

Expected outputs are a documented evidence-storage model and text-access
contract for the Energy Transition Monitoring system, tested plugins and
adapters, the corpus/question/provenance package, a runnable evaluation bench,
an operated Challenge with reproducible results, and research publications on
evidence lineage, failure mechanisms and method comparisons. These would extend the
[workshop deliverables](README.md#workshop-deliverables).

A credible team would combine energy-transition monitoring expertise,
information retrieval/NLP and document-processing research, research software
engineering, multilingual/domain expertise,
evaluation methods and researcher-facing studies. Libraries and tool
maintainers could contribute requirements, annotation, adoption and evaluation.
No organisation's participation is implied, including Zotero's.

### Consortium possibility raised by the author

Explore a consortium around AEDIST, Dan/Zotero and the #6012 work,
zotero-mcp, and zoteus. This is a list of prospective collaborators, not an
agreed partnership. Treat Zotero and #6012 as one platform contribution unless
their participants identify a different arrangement; a pull request is not
an additional institutional partner.

| Prospective contribution | Role to discuss |
|---|---|
| AEDIST research team | Energy Transition Monitoring use cases, evidence-storage requirements, scientific coordination and domain evaluation |
| Dan / Zotero, including #6012 | Native extraction and search expertise, sustainable interface design, platform compatibility and possible native uptake |
| zotero-mcp maintainers | An independent MCP integration, practical user workflows and before/after adaptation evidence |
| zoteus maintainers | Another consumer implementation, integration experience and comparative retrieval/operational tests |
| Evaluation and language specialists, to identify | Corpus and question annotation, multilingual analysis, independent protocol review and researcher studies |

Confirm which zotero-mcp implementation is intended before approaching anyone.
Map interested people and projects to their participating organisations, and
assess possible funded, associated or advisory roles against the selected
call. Do not assume that each maintainer needs to be a funded beneficiary or
that the proposed set already provides the required scientific expertise.

The useful complementarity is a platform, independent consumers and an
application-driven evaluation effort. Preserve independent assessment in the
Challenge: participating developers may contribute tasks and review the
protocol, but their own submissions need transparent adjudication and an
explicit conflict-of-interest arrangement. No contact or commitment has been
made on the strength of this note.

## Risks and alternatives

- Native Zotero capabilities may overtake a plugin. Preserve the scientific
  protocol and the consumer contract; allow the implementation to be replaced.
- Common extraction can introduce common errors. Retain independent source
  checks and compare alternative extraction paths where the experiment needs it.
- Participant selection and corpus composition can favour the workshop's own
  choices. Publish selection rules and limitations and seek external review.
- Tool adapters, user studies and Challenge support can consume the research
  budget. Separate scientific experiments from service operation when costing.
- The methods may prove incremental rather than novel. Conduct a focused
  prior-art review before treating the concept as a competitive research bid.

## Later assessment against the call

When a target call is selected, preserve this concept and assess it explicitly
against that call's current text. Do not infer eligibility from general thematic
similarity. The ANR [2027 work programme](https://anr.fr/en/work-programme-2027/)
is background to the discussion, not an instrument selection or fit verdict.

The assessment should settle:

- Scientific axis, instrument, expected novelty and fit to evaluation criteria.
- AEDIST's institutional framing and existing Energy Transition Monitoring
  architecture, coordinating organisation and eligible coordinator, along with
  confirmed partner roles and commitments.
- The evidence-storage boundary, historical-source retention needs and its
  interfaces to downstream claims, indicators and time series.
- Scope and measurable scientific contributions, including what generalises
  beyond Zotero and what remains engineering or community support.
- Work packages, staffing, equipment, Challenge operation, maintenance costs,
  duration, dependencies and the distinction between existing and proposed work.
- Data rights, licensing, ethics, privacy, open-science outputs and dissemination.
- Required application format, current deadlines, eligibility restrictions and
  any consortium or co-funding conditions.

Produce a fit/gap assessment and an explicit proceed, reshape or decline
recommendation before drafting the application. No submission or partner
outreach is authorised by this note.
