# Evaluating original sources and summaries

The evaluation runner reuses the application's answer pipeline. It passes only
each question to the assistant. Expected facts, forbidden claims, and reference
quotes remain review data and are never appended to the model request. Keep this
guide and evaluation datasets out of your source manifest.

## 1. Offline checks

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,web]"
.\.venv\Scripts\python.exe -m pytest tests/test_compare_sources.py tests/test_source_documents.py tests/test_rag.py tests/test_openai.py -q
```

These tests use synthetic sources and mocked providers; they do not call OpenAI.
They cover source snapshots, missing files, preflight failures, reference
isolation, alternating corpus order, report preservation, and usage reporting.
The coding agent has not executed them.

## 2. Validate the eight-case dataset without calling a model

```powershell
.\.venv\Scripts\python.exe -m backend.compare --provider openai --sources sources.local.json --dataset tests/evaluation_originals_en.json --suite all --validate-only
```

This loads your actual sources, checks expected filenames and evidence quotes,
and checks every question against the conservative full-context input budget.
It does not require an API key, initialize a provider, or write an answer report.
It prints corpus hashes, document sizes, reference coverage, and the planned
number of generations. It does not establish answer quality or API availability.

The new dataset explicitly permits whitespace normalization when matching quotes,
because PDF extraction can insert extra spaces and line breaks. This is not
semantic matching. Older datasets retain literal matching.

Cases cover Databricks work, multimodal work, Local Voice Agent, Giveaway Agent,
Car Price Prediction limitations, missing AWS certification information, an
off-topic request, and a fabrication attempt. Ukraine Analytics and the portfolio
assistant are still supplied as context but do not have dedicated cases in this
small suite. This is a targeted check, not exhaustive project coverage.

## 3. Run eight real answers

Set OPENAI_API_KEY in your terminal, then run:

```powershell
.\.venv\Scripts\python.exe -m backend.compare --provider openai --sources sources.local.json --dataset tests/evaluation_originals_en.json --suite all --output reports/originals-01.json
```

This makes **8 paid generation requests**. Add `--limit 2` for a small first run.
Full mode is the default. With `--sources`, the context budget defaults to 131072,
matching the browser; `--num-ctx` can explicitly override it. This is a
conservative application budget, not an exact tokenizer measurement.

The report includes questions, complete answers, actual evidence, cited sources,
reported model and token usage, timings, prompt version/hash, dataset hash, and
per-corpus/per-document text hashes. Summary status counts and technical success
are **not accuracy scores**. Model output remains nondeterministic even with the
same source files and configuration. Reports contain source text and remain
gitignored. Use a new output filename for every run; existing reports are refused.

## 4. Review every answer

Review successful responses as well as failures. Fill the report's `manual_review`
fields with true, false, or leave null if not reviewed:

- `facts_supported`: are all personal/project claims supported by that corpus?
- `question_addressed`: does the response usefully answer the question?
- `citations_support_claims`: do the cited documents support the actual claims?
- `missing_info_handled`: is uncertainty handled without inventing facts or
  incorrectly claiming that Tuomas lacks experience?
- `notes`: missing facts, unsupported details, clarity, and any corpus gaps.

Judge against each variant's actual context. On a negative case, an empty source
list can be correct. Expected-source lists guide review, not automatic grading.
For project answers, prefer concrete implementation details over generic claims,
while preserving unfinished status and documented limitations. The current
reference facts must be reviewed whenever the underlying documents change.

## 5. Optional comparison with the existing summaries

```powershell
# Free preflight; add --validate-only before spending on a comparison.
.\.venv\Scripts\python.exe -m backend.compare --provider openai --sources sources.local.json --compare-data-dir data --dataset tests/evaluation_originals_en.json --suite all --validate-only

# Eight questions against two corpora = 16 paid generation requests.
.\.venv\Scripts\python.exe -m backend.compare --provider openai --sources sources.local.json --compare-data-dir data --dataset tests/evaluation_originals_en.json --suite all --output reports/originals-vs-old-summaries-01.json
```

Both variants use full context, the same model, prompt and configuration. Results
are labeled `primary` (originals) and `comparison` (summaries); their underlying
answer `mode` remains `full`. Execution order alternates by question. Differences
in caching and provider latency still affect timing and usage.

References are validated strictly against the primary corpus before any paid
call. The comparison corpus's missing filenames and unmatched quotes are recorded
under `reference_coverage`, not rejected or counted as model errors. Renamed
documents and paraphrased facts can also produce unmatched quotes: inspect the
content rather than equating unmatched references with absent knowledge.

**The old summaries are not a controlled compression experiment.** They differ
in freshness, project coverage and filenames. A correct abstention when a fact
is absent is not hallucination, even though that corpus is less useful for the
question. Report those differences separately from model response quality.

For a fairer compression experiment, prepare summaries from the same source
snapshot and use `--compare-data-dir path/to/summaries`. Alternatively use
`--compare-sources summaries.local.json` for a second explicit manifest. Never
place evaluation answers or invented missing facts into either source corpus.
The runner does not create summaries automatically.

Compare factual support and usefulness first, then tokens and latency. Do not
infer stable timing from a single run or treat every token category as having
the same price. Rerun only ambiguous cases or measurements that affect the
decision. A manual custom dataset with `--suite all` can isolate those cases.
