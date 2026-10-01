"""Ask one independent portfolio question using Ollama."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from backend.config import LLMConfig
from backend.llm import OllamaClient
from backend.rag import PortfolioAssistant


def add_options(parser: argparse.ArgumentParser) -> None:
    defaults = LLMConfig()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--db-dir", type=Path, default=Path("vector_db"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default=defaults.model)
    parser.add_argument("--ollama-url", default=defaults.base_url)
    parser.add_argument("--timeout", type=float, default=defaults.timeout_seconds)
    parser.add_argument("--num-ctx", type=int, default=defaults.num_ctx)
    parser.add_argument("--max-output-tokens", type=int, default=defaults.max_output_tokens)


def llm_config(args: argparse.Namespace) -> LLMConfig:
    return LLMConfig(model=args.model, base_url=args.ollama_url, timeout_seconds=args.timeout,
                     num_ctx=args.num_ctx, max_output_tokens=args.max_output_tokens)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--mode", choices=["full", "rag"], default="rag")
    parser.add_argument("--json", action="store_true", dest="as_json")
    add_options(parser)
    args = parser.parse_args(argv)
    try:
        config = llm_config(args)
        if not args.question.strip() or len(args.question.strip()) > config.max_question_chars:
            raise ValueError(f"Provide a question of 1–{config.max_question_chars} characters")
        assistant = PortfolioAssistant(OllamaClient(config), config, mode=args.mode,
                                       data_dir=args.data_dir, db_dir=args.db_dir, top_k=args.top_k)
        result = assistant.ask(args.question)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Question failed: {exc}\n")
    if args.as_json:
        print(json.dumps(asdict(result), ensure_ascii=True, indent=2))
    else:
        print(f"Mode: {result.mode} | Status: {result.status}\n\n{result.answer}\n\nSources:")
        if not result.sources:
            print("No cited sources.")
        for source in result.sources:
            print(f"[{source.source_id}] {source.source} — {source.title}")
            if source.section:
                print(f"  Section: {source.section}")
        print(f"\nTime: {result.elapsed_seconds:.2f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
