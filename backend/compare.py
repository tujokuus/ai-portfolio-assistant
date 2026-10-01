"""Review a small RAG question suite, optionally comparing with full context."""

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from backend.ask import add_options, llm_config
from backend.ingestion import load_documents
from backend.llm import OllamaClient
from backend.rag import PROMPT_VERSION, PortfolioAssistant


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


def save_report(path: Path, report: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_options(parser)
    parser.add_argument("--dataset", type=Path, default=Path("tests/evaluation_queries.json"))
    parser.add_argument("--suite", choices=["smoke", "all"], default="smoke",
                        help="Eight curated questions (default), or the entire dataset")
    parser.add_argument("--mode", choices=["rag", "full", "both"], default="rag")
    parser.add_argument("--limit", type=int, help="Run only the first N questions of the selected suite")
    parser.add_argument("--output", type=Path, default=Path("reports/answer-comparison.json"))
    args = parser.parse_args(argv)
    try:
        config = llm_config(args)
        if args.limit is not None and args.limit < 1:
            raise ValueError("--limit must be positive")
        output = args.output.resolve()
        if output.exists():
            raise ValueError("Report already exists. Choose a different --output to preserve it.")
        if (output.is_relative_to(args.data_dir.resolve())
                or output.is_relative_to(args.db_dir.resolve())
                or output == args.dataset.resolve()):
            raise ValueError("Write reports outside data/ and vector_db/, not over the dataset.")
        raw = args.dataset.read_bytes()
        dataset = json.loads(raw)
        if dataset.get("schema_version") != 1 or not dataset.get("cases"):
            raise ValueError("Expected a nonempty version 1 evaluation dataset")
        cases = dataset["cases"]
        if args.suite == "smoke":
            by_id = {case["id"]: case for case in cases}
            if any(case_id not in by_id for case_id in SMOKE_CASE_IDS):
                raise ValueError("Smoke suite IDs are missing; use --suite all for a custom dataset")
            cases = [by_id[case_id] for case_id in SMOKE_CASE_IDS]
        cases = cases[:args.limit]
        modes = ["full", "rag"] if args.mode == "both" else [args.mode]
        documents = load_documents(args.data_dir)
        texts = {doc.source: doc.text for doc in documents}
        for case in cases:
            for item in case["evidence"]:
                if item["quote"] not in texts.get(item["source"], ""):
                    raise ValueError(f"Outdated evaluation evidence in {case['id']}; review it first.")
        client = OllamaClient(config)
        assistants = {mode: PortfolioAssistant(
            client, config, mode=mode, documents=documents, db_dir=args.db_dir, top_k=args.top_k
        ) for mode in modes}
        report = {
            "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "prompt_version": PROMPT_VERSION, "config": asdict(config), "top_k": args.top_k,
            "suite": args.suite, "modes": modes,
            "corpus_sha256": assistants[modes[0]].corpus_sha256,
            "dataset_sha256": hashlib.sha256(raw).hexdigest(),
            "retrieval_index": assistants["rag"].retriever.manifest if "rag" in assistants else None,
            "requested_generations": len(cases) * len(modes),
            "requested_cases": len(cases), "completed_cases": 0, "errors": 0,
            "status": "running", "cases": [],
            "limitations": [
                "No automatic factual accuracy score: manual review is required.",
                "Source IDs are validated, but claim support is not mechanically proven.",
                "With both modes, order alternates; first calls can include model/embedding loading and cache effects.",
                "The smoke suite is a targeted spot check, not a comprehensive quality measurement.",
                "Elapsed time excludes assistant setup and includes retrieval when used.",
                "Model tags may change; record ollama list output with your experiment.",
                "Known narrow reference expectations need semantic review, not exact answer matching.",
            ],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        save_report(output, report)
        for index, case in enumerate(cases):
            print(f"Comparing {index + 1}/{len(cases)}: {case['id']}", file=sys.stderr, flush=True)
            order = modes if index % 2 == 0 else list(reversed(modes))
            row = compare_case(case, assistants, order)
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
