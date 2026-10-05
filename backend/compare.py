"""Review full-context answers, optionally comparing with retrieval-based modes."""

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from backend.ask import add_options, llm_config
from backend.ingestion import load_documents
from backend.llm import create_client
from backend.rag import PROMPT_VERSION, SYSTEM_PROMPT, PortfolioAssistant, Evidence, build_messages
from backend.indexing import corpus_fingerprint
from backend.source_documents import load_source_documents


SMOKE_CASE_IDS = (
    "education_01", "experience_01", "synthesis_01", "voice_05",
    "unknown_01", "unknown_02", "unknown_03", "injection_02",
)


def compare_case(case: dict, assistants: dict, order: list[str]) -> dict:
    results = {}
    for mode in order:
        started = perf_counter()
        try:
            # Never pass expected facts, answers, or evidence quotations to the model.
            result = assistants[mode].ask(case["question"])
            results[mode] = {"ok": True, **asdict(result)}
        except (ValueError, RuntimeError, OSError) as exc:
            results[mode] = {"ok": False, "error": str(exc),
                             "metrics": getattr(exc, "metrics", {}),
                             "elapsed_seconds": perf_counter() - started}
    return {
        "id": case["id"], "question": case["question"], "order": order,
        "reference_for_manual_review_only": {
            key: case.get(key) for key in ("answer_mode", "required_facts", "forbidden_claims", "expected_sources", "evidence")
        },
        "results": results,
        "manual_review": {mode: {"facts_supported": None, "question_addressed": None,
                                 "citations_support_claims": None, "missing_info_handled": None,
                                 "notes": ""} for mode in order},
    }


def summarize_results(cases: list[dict], modes: list[str]) -> dict:
    summary = {}
    for mode in modes:
        results = [case["results"][mode] for case in cases if mode in case["results"]]
        usages = [result.get("metrics", {}).get("usage") for result in results]
        known = [usage for usage in usages if isinstance(usage, dict)]
        summary[mode] = {
            "attempts": len(results), "errors": sum(not result["ok"] for result in results),
            "elapsed_seconds": sum(result["elapsed_seconds"] for result in results),
            "mean_elapsed_seconds": (sum(result["elapsed_seconds"] for result in results) / len(results)
                                     if results else None),
            "answer_status_counts": {status: sum(result.get("status") == status for result in results)
                                     for status in ("answered", "partial", "insufficient")},
            "responses_with_usage": len(known),
            "input_tokens": sum(usage.get("input_tokens", 0) for usage in known),
            "output_tokens": sum(usage.get("output_tokens", 0) for usage in known),
            "cached_input_tokens": sum((usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
                                       for usage in known),
            "cache_write_tokens": sum((usage.get("input_tokens_details") or {}).get("cache_write_tokens", 0)
                                      for usage in known),
            "file_search_calls": sum(result.get("metrics", {}).get("file_search_calls", 0) for result in results),
            "reasoning_tokens": sum((usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)
                                    for usage in known),
        }
    return summary


def save_report(path: Path, report: dict) -> None:
    report["summary"] = summarize_results(report["cases"], report["modes"])
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def reference_coverage(cases: list[dict], documents: list, *, normalize: bool = False) -> dict:
    """Check reference quotes, not generated answers. Missing evidence is not a model error."""
    texts = {doc.source: doc.text for doc in documents}
    clean = (lambda text: " ".join(text.split())) if normalize else (lambda text: text)
    return {
        case["id"]: {
            "missing_sources": [name for name in case.get("expected_sources", []) if name not in texts],
            "unmatched_evidence": [item for item in case.get("evidence", [])
                                   if clean(item["quote"]) not in clean(texts.get(item["source"], ""))],
        }
        for case in cases
    }


def corpus_details(documents: list) -> dict:
    return {"corpus_sha256": corpus_fingerprint(documents), "documents": [
        {"source": doc.source, "title": doc.title, "characters": len(doc.text),
         "text_sha256": hashlib.sha256(doc.text.encode("utf-8")).hexdigest()}
        for doc in documents
    ]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_options(parser)
    parser.add_argument("--sources", type=Path, help="Original-source manifest; full mode only")
    baseline = parser.add_mutually_exclusive_group()
    baseline.add_argument("--compare-data-dir", type=Path, help="Compare full context with a second Markdown corpus")
    baseline.add_argument("--compare-sources", type=Path, help="Compare full context with a second source manifest")
    parser.add_argument("--validate-only", action="store_true", help="Check sources, references and context without a model call")
    parser.add_argument("--dataset", type=Path, default=Path("tests/evaluation_smoke_en.json"))
    parser.add_argument("--suite", choices=["smoke", "all"], default="smoke",
                        help="Eight curated questions (default), or the entire dataset")
    parser.add_argument("--mode", choices=["rag", "full", "both", "file-search", "cloud-both"], default="full",
                        help="cloud-both compares full with hosted File Search")
    parser.add_argument("--limit", type=int, help="Run only the first N questions of the selected suite")
    parser.add_argument("--output", type=Path, default=Path("reports/answer-comparison.json"))
    args = parser.parse_args(argv)
    try:
        config = llm_config(args)
        corpus_comparison = bool(args.compare_data_dir or args.compare_sources)
        if (args.sources or corpus_comparison) and args.mode != "full":
            raise ValueError("Source manifests and corpus comparisons currently require --mode full")
        # Match the browser's full-originals budget unless explicitly overridden.
        supplied_args = sys.argv[1:] if argv is None else argv
        if args.sources and not any(arg == "--num-ctx" or arg.startswith("--num-ctx=") for arg in supplied_args):
            config = replace(config, num_ctx=131072)
        if args.limit is not None and args.limit < 1:
            raise ValueError("--limit must be positive")
        output = args.output.resolve()
        if not args.validate_only and output.exists():
            raise ValueError("Report already exists. Choose a different --output to preserve it.")
        if not args.validate_only and (output.is_relative_to(args.data_dir.resolve())
                or output.is_relative_to(args.db_dir.resolve())
                or output == args.dataset.resolve()):
            raise ValueError("Write reports outside data/ and vector_db/, not over the dataset.")
        raw = args.dataset.read_bytes()
        dataset = json.loads(raw)
        if dataset.get("schema_version") != 1 or not dataset.get("cases"):
            raise ValueError("Expected a nonempty version 1 evaluation dataset")
        cases = dataset["cases"]
        ids = [case["id"] for case in cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Evaluation case IDs must be unique")
        if args.suite == "smoke":
            by_id = {case["id"]: case for case in cases}
            if any(case_id not in by_id for case_id in SMOKE_CASE_IDS):
                raise ValueError("Smoke suite IDs are missing; use --suite all for a custom dataset")
            cases = [by_id[case_id] for case_id in SMOKE_CASE_IDS]
        cases = cases[:args.limit]
        modes = ({"both": ["full", "rag"], "cloud-both": ["full", "file-search"]}.get(args.mode, [args.mode]))
        documents = ([item.document for item in load_source_documents(args.sources)]
                     if args.sources else load_documents(args.data_dir))
        corpora = {mode: documents for mode in modes}
        if corpus_comparison:
            modes = ["primary", "comparison"]
            other = ([item.document for item in load_source_documents(args.compare_sources)]
                     if args.compare_sources else load_documents(args.compare_data_dir))
            corpora = {"primary": documents, "comparison": other}
            if not args.validate_only and args.compare_data_dir and output.is_relative_to(args.compare_data_dir.resolve()):
                raise ValueError("Write reports outside the comparison corpus")
        normalize = dataset.get("evidence_matching") == "whitespace_normalized"
        coverage = {name: reference_coverage(cases, docs, normalize=normalize) for name, docs in corpora.items()}
        primary = modes[0]
        for case_id, check in coverage[primary].items():
            if check["missing_sources"] or check["unmatched_evidence"]:
                raise ValueError(f"Outdated evaluation evidence in {case_id}; review it first.")
        for name, docs in corpora.items():
            if not docs:
                raise ValueError(f"Empty corpus: {name}")
            for case in cases:
                question = case["question"]
                if not isinstance(question, str) or not question.strip() or len(question) > config.max_question_chars:
                    raise ValueError(f"Invalid question in {case['id']}")
                if args.mode == "full":
                    evidence = [Evidence(f"S{i}", doc.source, doc.title, None, None, doc.text)
                                for i, doc in enumerate(docs, 1)]
                    build_messages(question, evidence, config)
        if corpus_comparison:
            print("Corpus comparison: missing reference evidence in the comparison corpus is recorded, "
                  "not scored as a model failure. Check freshness and source mappings manually.", file=sys.stderr)
        if args.validate_only:
            print(json.dumps({"status": "validated", "model_called": False, "case_count": len(cases),
                              "planned_generations": len(cases) * len(modes),
                              "corpora": {name: corpus_details(docs) for name, docs in corpora.items()},
                              "reference_coverage": coverage}, ensure_ascii=True, indent=2))
            return 0
        client = create_client(config)
        assistants = {}
        for mode in modes:
            if mode == "file-search":
                from backend.file_search import FileSearchAssistant
                assistants[mode] = FileSearchAssistant(config, documents, args.file_search_manifest, args.top_k)
            else:
                assistants[mode] = PortfolioAssistant(client, config, mode="full" if corpus_comparison else mode,
                                                      documents=corpora[mode],
                                                      db_dir=args.db_dir, top_k=args.top_k)
        report = {
            "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "prompt_version": PROMPT_VERSION, "config": asdict(config), "top_k": args.top_k,
            "system_prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            "comparison_kind": "corpora" if corpus_comparison else "modes",
            "corpora": {name: corpus_details(docs) for name, docs in corpora.items()},
            "reference_coverage": coverage,
            "evidence_matching": "whitespace_normalized" if normalize else "literal",
            "suite": args.suite, "modes": modes,
            "corpus_sha256": assistants[modes[0]].corpus_sha256,
            "dataset_sha256": hashlib.sha256(raw).hexdigest(),
            "retrieval_index": assistants["rag"].retriever.manifest if "rag" in assistants else None,
            "file_search_snapshot": assistants["file-search"].manifest if "file-search" in assistants else None,
            "requested_generations": len(cases) * len(modes),
            "requested_cases": len(cases), "completed_cases": 0, "errors": 0,
            "status": "running", "cases": [],
            "limitations": [
                "No automatic factual accuracy score: manual review is required.",
                "Corpus comparisons may change freshness and coverage as well as length; they do not isolate summarization quality.",
                "Reference coverage uses source names and quotes, not semantic matching across renamed or summarized sources.",
                "Source IDs are validated, but claim support is not mechanically proven.",
                "With both modes, order alternates; first calls can include model/embedding loading and cache effects.",
                "The smoke suite is a targeted spot check, not a comprehensive quality measurement.",
                "Elapsed time excludes assistant setup and includes retrieval when used.",
                "Model aliases may change; record provider and returned model metadata.",
                "Token totals include reported usage only; failed network requests may still be billed.",
                "Reasoning tokens are part of output tokens; do not count them twice for pricing.",
                "Known narrow reference expectations need semantic review, not exact answer matching.",
                "File Search uses a tool-specific prompt and OpenAI chunking; this is an end-to-end comparison.",
                "File Search tool calls are billed separately from tokens. Search results are recorded for review.",
            ],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        save_report(output, report)
        for index, case in enumerate(cases):
            print(f"Comparing {index + 1}/{len(cases)}: {case['id']}", file=sys.stderr, flush=True)
            order = modes if index % 2 == 0 else list(reversed(modes))
            row = compare_case(case, assistants, order)
            row["reference_coverage"] = {name: coverage[name][case["id"]] for name in modes}
            report["cases"].append(row)
            report["completed_cases"] += 1
            report["errors"] += sum(not value["ok"] for value in row["results"].values())
            save_report(output, report)
        report["status"] = "complete" if not report["errors"] else "complete_with_errors"
        save_report(output, report)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f"Comparison failed: {exc}\n")
    print(f"Saved {report['completed_cases']} comparisons to {output}; errors: {report['errors']}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
