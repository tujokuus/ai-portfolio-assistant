# Portfolio evaluation cases

`evaluation_queries.json` contains 30 hand-authored cases based on the nine real
portfolio Markdown documents currently in `data/`. Questions are mostly Finnish,
with three English cases, while the sources are English. This intentionally
includes cross-language retrieval. Document content was read locally; upstream
CV, portfolio pages, repositories, and code were not independently re-verified
when authoring this dataset.

## Scope and use

This is a small development evaluation set, not an independent benchmark or a
claim of retrieval quality. No embedding search or generated-answer evaluation
has been run. Cases cover direct facts, technical descriptions, paraphrases,
personal contributions, multiple sources, incomplete information, false premises,
future versus completed work, and two prompt injection attempts.

Keep this file and the JSON outside `data/`. Do not embed questions, expected
answers, forbidden claims, or the source review checklist as portfolio knowledge.
The intentionally unsupported claims in the evaluation are test inputs, not facts.

The synthetic sample documents have been removed. They and the user-deleted
experience documents are not used as expected evidence or restored.

## Field meanings

- `id`: Stable evaluation case identifier, independent of chunking settings.
- `category`: The main behavior exercised by the case.
- `question`: The exact question to submit; use it unchanged when comparing runs.
- `answer_mode`: `answer` for a supported answer; `partial_answer` for supported
  details plus explicit limits; `correct_premise` for a source-backed correction;
  `abstain` when the requested fact cannot be established. Abstention may explain
  a documented limitation and cite it; it does not always mean empty retrieval.
- `expected_sources`: Paths relative to `data/` representing the reference
  evidence set. Multi-source cases require more than one source to support the
  listed facts. These are not an exclusive whitelist: equivalent evidence in
  other portfolio documents can be valid and deserves manual review.
- `required_facts`: Semantic requirements, including necessary qualifications or
  statements that information is unavailable. These are not exact-match strings;
  synonyms and accurate translations are acceptable.
- `forbidden_claims`: Unsupported assertions or overstatements to avoid. Evaluate
  meaning, not word presence: explicitly denying that a claim is supported is
  acceptable, even if the answer mentions that claim.
- `evidence`: Verbatim snippets with source path and section heading. These allow
  review of expectations and help check whether a retrieved chunk contains the
  actual evidence, rather than just coming from the right document. A fact may
  require combining several snippets. Missing facts have no positive evidence;
  their absence was checked against the current curated corpus.
- `review_note`: Additional guidance where a case needs it.

Do not use similarity scores as probabilities of correctness. Do not automatically
fail an abstention case because retrieval found vaguely related documents.

## Phase 2: retrieval evaluation (implemented, not yet executed)

After building the index, run:

```powershell
.\.venv\Scripts\python.exe -m backend.evaluation --top-k 5 --output reports/retrieval.json
```

The report includes each question's retrieved text and metadata for manual review,
source recall, all-sources-found rate, and a literal-evidence diagnostic. Summary
recalls are macro averages over scored cases. Evidence is checked as a normalized
whitespace substring within a single chunk from the reference source. This is a
deliberately conservative diagnostic: quotes split across chunks are missed even
if the complete evidence was retrieved. It is not a semantic correctness metric.
The command rejects a stale corpus fingerprint and outdated reference quotations.
No evaluation results have been measured yet, at the user's request.

For cases with expected sources, record which reference sources appear in the top
5 chunks, source recall (found reference sources / all reference sources), and
whether all reference sources were found. Also inspect the actual chunk text and
its metadata against the evidence snippets. Finding the right filename is not
enough, and exact snippet matching alone can miss evidence split across chunks.

Cases with empty expected sources have no source-recall denominator. Exclude them
from that metric and retain them for answerability evaluation in Phase 3. Cases
with a documented limitation can still test retrieval of that limitation even
when their answer mode is `abstain`.

Because several questions share documents, results are correlated. Keep some new,
user-written questions aside for a later check after retrieval tuning, rather than
treating scores on this development set as unbiased performance estimates.

## Phase 3: answer evaluation (later, not implemented here)

Review whether each answer includes the required facts, preserves uncertainty,
avoids unsupported assertions, and cites evidence actually supporting its claims.
For multi-source answers, check all necessary sources. Judge facts semantically
rather than requiring a single reference sentence or fixed answer language.
Neither passing mocked LLM tests nor matching citations proves answer faithfulness.
Two injection cases provide regression coverage, not a security guarantee.

## Maintenance and current limitations

Tuomas should review personal-contribution and status expectations. The existing
`source-review-checklist.md` contains unresolved questions about titles, dates,
metrics, and implementation details; it is not used as factual answer evidence.
This dataset avoids inventing answers to those questions. Missing-information
cases are specific to today's corpus and must be reviewed when documents are added.

Run the reference-integrity checks with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_evaluation_dataset.py -q
```

They validate unique IDs, modes, required fields, source files, and verbatim
evidence in the indicated sections. They do not verify that the original sources
are truthful, that every expected fact follows logically, or that missing facts
remain absent after additions. An evidence-text edit intentionally fails a check
so the corresponding expectation can be reviewed.
