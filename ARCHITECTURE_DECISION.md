# Choosing full context for a small portfolio assistant

Decision date: 2 October 2026. Status: selected for the first application version;
broader validation and deployment are still pending.

## Decision and motivation

This project compares three ways to ground a chatbot in a curated professional
portfolio: full context, local retrieval-augmented generation (RAG), and OpenAI
hosted File Search. The selected configuration is full context with OpenAI
`gpt-6-luna`: send the complete portfolio with each question and require
source-backed, structured answers.

For the current small corpus, the measured full-context implementation was faster
and cheaper than hosted File Search, with comparable factual quality in a small
manual review. It also avoids a retrieval step that can omit essential evidence.
This is a workload-specific engineering decision, not a claim that full context
is universally better than RAG or that this is the cheapest model available.

## Implementations explored

| Approach | Evidence supplied to the answer model | Operational tradeoff |
|---|---|---|
| Full context | All curated Markdown/text documents, with source IDs | Simple to update and inspect; input grows with the corpus |
| Local RAG | Top-ranked chunks from Chroma using multilingual E5 embeddings | Controls indexing and retrieval locally; adds model loading, indexing and retrieval maintenance |
| Hosted File Search | Results selected by OpenAI's file-search tool from an uploaded vector store | Offloads indexing and search; adds tool fees, remote snapshot management and retrieval latency |

Local Ollama generation (`qwen3:4b-instruct`) was used during prototyping. Its
evaluations exposed invalid answer structures, unnecessary abstentions and
language-instruction failures. OpenAI generation was then added behind the same
client interface. The earlier local-RAG tests also exposed retrieval failures:
finding the right file did not always mean finding the necessary section.

Generation and retrieval are separate components. A missed source chunk is a
retrieval problem; rejecting available evidence is an answer-generation problem.
Changing the answer model alone cannot guarantee that missing evidence is found.

## Comparable cloud experiment

The cloud comparison used the same `gpt-6-luna` model, English scope policy
(`portfolio-grounding-v4-scope`), output limit of 1,024 tokens and requested
reasoning effort `none`. Four questions were run once in each mode, alternating
mode order. The dataset is [evaluation_cloud_four.json](tests/evaluation_cloud_four.json).
It covers factual experience, synthesis across two projects, a false premise,
and a completely unrelated request. Reference expectations were kept outside
model input. Citations were checked against supplied or retrieved evidence IDs,
then answers were manually reviewed for actual support and completeness.

Full and File Search share core instructions but require different evidence and
citation instructions. The test compares complete implementations, not just the
search algorithms in isolation. No local RAG result is included in this table:
its earlier runs were not a matched three-way benchmark.

| Measurement across four questions | Full context | Hosted File Search |
|---|---:|---:|
| Completed requests without technical errors | 4/4 | 4/4 |
| Sum of per-question elapsed times | 11.95 s | 17.80 s |
| Mean elapsed time | 2.99 s | 4.45 s |
| Input tokens | 15,227 | 16,532 |
| Output tokens (including reported reasoning) | 453 | 736 |
| Cached input tokens | 0 | 6,489 |
| Cache-write tokens | 15,215 | 2,238 |
| File Search tool calls | 0 | 3 |
| Estimated request cost, USD | $0.00213 | $0.00899 |

Full context was faster in all four observed pairs. Technical success is not an
accuracy score, and these measurements do not establish production latency.

## What the answers showed

- **Databricks:** both described supported pipeline and orchestration work and
  cited the employment document. Both omitted Apache Spark, an expected detail
  in the evaluation reference; the core answer was correct but not exhaustive.
- **Project comparison:** both used the correct two sources and preserved the
  projects' unfinished status. Full included bronze/silver/gold layers; File
  Search gave a clear conceptual comparison but omitted those named layers.
- **False premise:** both correctly explained that cross-session embeddings were
  outside Local Voice Agent's documented initial scope. Full returned a direct
  `answered` correction. File Search returned `partial` and an unnecessary extra
  missing-information paragraph.
- **Unrelated recipe:** neither supplied a recipe or invented a portfolio link.
  File Search gave the better scope explanation and made no search call. Full
  described missing recipe information rather than clearly redirecting to the
  portfolio, leaving a wording improvement for a future prompt revision.

File Search did not reduce input tokens in this experiment. It returned five
results for each portfolio question, often containing entire short documents and
some irrelevant material. Tool definitions and the tool workflow also contribute
input. Retrieval overhead can outweigh evidence reduction when the corpus is
already small. Reducing result counts might help but has not been evaluated here.

## Cost calculation and provenance

Estimates use standard short-context Luna rates checked on 2 October 2026:
$0.10 ordinary input, $0.01 cached input, $0.125 cache writes and $0.50 output per
million tokens; File Search adds $0.0025 per tool call. Cache reads and writes are
subsets of input, and reported reasoning tokens are already included in output.

`cost = ((input - cached - cache_write) * 0.10 + cached * 0.01
        + cache_write * 0.125 + output * 0.50) / 1,000,000
        + file_search_calls * 0.0025`

The estimated combined experiment cost is $0.01112. These are usage-based
estimates, not invoices; taxes, hosting, upload/storage charges and regional
surcharges are excluded. See [model pricing](https://developers.openai.com/api/docs/models/gpt-6-luna)
and [tool pricing](https://developers.openai.com/api/docs/pricing). Prices can change.

The original local report is `reports/full-vs-file-search-01.json` (not committed).
Its dataset SHA-256 is
`85b3612b56860a55f08cabdae0f91efb2fbbca728d8c19a82176bf2a88402ee6`
and corpus SHA-256 is
`0494dcd67155ccd5b8c17c3491c3b1052cc5c194d0eafd2a1ddabca0706bdc4a`.
The public summary excludes account resource IDs and raw logs. The test dataset
and implementation remain in the repository for reproduction with an API account.

## Limits and when to revisit

Four questions with one run per mode are a spot check, not a statistically robust
benchmark. Cache conditions differed, model aliases may change, and the test has
no concurrent users. Timings exclude initial uploads, indexing and assistant
setup. No general accuracy percentage or production readiness is claimed.

Full context remains bounded by the application's conservative input budget;
it must not silently truncate documents. Revisit retrieval if the corpus grows,
token cost becomes significant, users need separate access-controlled collections,
or a broader evaluation shows relevant evidence is being missed in full context.
Full context also needs evidence-grounding and scope checks: supplying all files
does not guarantee the model uses them correctly.

## Next validation and delivery steps

1. Run the five-case [full-context follow-up](tests/evaluation_full_followup.json)
   for education, image analysis, missing certifications, confidential metrics
   and an instruction to invent credentials. Review content and citations.
2. Address observed failures and rerun only the affected cases before broadening
   evaluation. Keep results and prompt versions distinct from this baseline.
3. Add a backend endpoint and a small chat UI showing answers and sources.
   Keep API credentials server-side and bound request/output sizes and usage.
4. Validate response time and errors through the actual UI, then deploy a small
   pilot. Conversation memory, multi-turn evaluation and streaming are separate
   future features; current CLI requests are independent.

The main outcome is a justified simplification: implementing and evaluating
retrieval made it possible to choose a smaller operational design for this corpus,
while retaining both retrieval implementations for future comparison.
