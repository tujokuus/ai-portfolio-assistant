"""Evaluate source recall and an explicitly limited literal-evidence diagnostic."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from backend.indexing import corpus_fingerprint
from backend.ingestion import load_documents
from backend.retrieval import Retriever


def evaluate_cases(cases: list[dict], retriever, top_k: int = 5) -> dict:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    rows = []
    for case in cases:
        # Only the question is sent to retrieval, never reference answers/evidence.
        results = retriever.search(case["question"], top_k)
        expected = set(case["expected_sources"])
        found = {result.chunk.source for result in results}
        evidence = case["evidence"]
        exact_hits = sum(any(
            result.chunk.source == item["source"]
            and " ".join(item["quote"].split()) in " ".join(result.chunk.text.split())
            for result in results
        ) for item in evidence)
        rows.append({
            "id": case["id"], "question": case["question"],
            "answer_mode": case["answer_mode"],
            "expected_sources": sorted(expected), "retrieved_sources": sorted(found),
            "missing_sources": sorted(expected - found),
            "source_recall": len(expected & found) / len(expected) if expected else None,
            "all_sources_found": expected <= found if expected else None,
            "literal_evidence_recall": exact_hits / len(evidence) if evidence else None,
            "results": [asdict(result) for result in results],
        })
    scored = [row for row in rows if row["source_recall"] is not None]
    evidence_scored = [row for row in rows if row["literal_evidence_recall"] is not None]
    return {
        "top_k": top_k, "case_count": len(rows), "source_scored_cases": len(scored),
        "unscored_cases": len(rows) - len(scored),
        "mean_source_recall": sum(row["source_recall"] for row in scored) / len(scored) if scored else None,
        "all_sources_found_rate": sum(row["all_sources_found"] for row in scored) / len(scored) if scored else None,
        "mean_literal_evidence_recall": (
            sum(row["literal_evidence_recall"] for row in evidence_scored) / len(evidence_scored)
            if evidence_scored else None
        ),
        "limitations": [
            "Source recall measures retrieval of reference files, not answer correctness.",
            "Literal evidence recall misses quotations split across chunks or expressed differently.",
            "Cases with no expected sources are unscored, not passes or failures.",
            "No generation, abstention, or injection-resistance behavior is evaluated in Phase 2.",
        ],
        "cases": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("tests/evaluation_queries.json"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--db-dir", type=Path, default=Path("vector_db"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, help="Optional JSON report; stdout otherwise")
    args = parser.parse_args(argv)
    try:
        if args.top_k < 1:
            raise ValueError("top_k must be positive")
        if args.output:
            output = args.output.resolve()
            if output == args.dataset.resolve() or output.is_relative_to(args.data_dir.resolve()):
                raise ValueError("Write reports outside data/ and do not overwrite the evaluation dataset")
        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        if dataset.get("schema_version") != 1:
            raise ValueError("Unsupported evaluation dataset schema")
        retriever = Retriever(args.db_dir)
        documents = load_documents(args.data_dir)
        if corpus_fingerprint(documents) != retriever.manifest["corpus_sha256"]:
            raise ValueError("Source documents changed since indexing. Rebuild before evaluation.")
        by_source = {document.source: document.text for document in documents}
        for case in dataset["cases"]:
            for source in case["expected_sources"]:
                if source not in by_source:
                    raise ValueError(f"Evaluation case {case['id']} references missing source {source}")
            for evidence in case["evidence"]:
                if evidence["quote"] not in by_source.get(evidence["source"], ""):
                    raise ValueError(f"Review outdated evidence in evaluation case {case['id']}")
        report = evaluate_cases(dataset["cases"], retriever, args.top_k)
        report["index"] = retriever.manifest
        serialized = json.dumps(report, ensure_ascii=True, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized + "\n", encoding="utf-8")
            print(f"Report saved to {args.output}")
            print(json.dumps({key: value for key, value in report.items() if key not in {"cases", "index"}}, indent=2))
        else:
            print(serialized)
    except Exception as exc:
        parser.exit(1, f"Evaluation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
