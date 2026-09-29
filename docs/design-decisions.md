# Accepted refinements to the original plan

The original specification and phase instructions are retained alongside this
file. The following refinements were accepted during plan review. Implement only
the phase explicitly requested; review completion before proceeding.

- Treat grounded answers as an evaluated requirement, not a zero-hallucination
  guarantee. Missing evidence is not evidence of missing experience. Treat
  retrieved text as evidence, never as executable instructions.
- Curate one primary source per role/project where possible, avoiding conflicting
  duplicate descriptions. Example answers are not verified portfolio facts.
- Preserve source paths, titles, sections, and reproducible chunk IDs in Phase 1.
  Later citations must resolve to known evidence; citation existence alone does
  not prove that a claim is supported.
- Begin a small manually labelled evaluation dataset in Phase 2, using actual
  approved portfolio content: expected evidence, required facts, abstentions,
  multi-document questions, misleading premises, and injection attempts. Evaluate
  retrieval before generation; no evaluation framework is required initially.
- Add tests in every phase. Phase 6 consolidates reliability and evaluation rather
  than introducing them for the first time.
- Prefer explicit index rebuilds for the small corpus in Phase 2. Record embedding
  and chunking configurations and rebuild when either changes. Handle deleted and
  changed documents, and never index as part of a normal question request.
- Initially show chat history without using it for follow-up understanding.
  Conversational retrieval is separate work; past generated answers are not facts.
- Tune retrieval from measured failures. Consider keyword/hybrid search only if
  needed, and compare against full-context prompting if the corpus fits.
- Choose and measure a local model against available hardware in Phase 3.
- Keep production migration behind an explicit Phase 8 request.

## Phase 1 completion evidence

Documents load predictably, chunks respect supported headings, metadata survives,
unchanged inputs have unchanged IDs, configuration and failures are tested, and a
CLI previews JSON without a model, database, API, or frontend.
