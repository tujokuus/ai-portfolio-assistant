"""Ask one independent portfolio question using Ollama or OpenAI."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from backend.config import LLMConfig
from backend.llm import create_client
from backend.rag import PortfolioAssistant


def add_options(parser: argparse.ArgumentParser) -> None:
    defaults = LLMConfig()
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--db-dir", type=Path, default=Path("vector_db"))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--provider", choices=["ollama", "openai"], default="ollama")
    parser.add_argument("--model", help="Default: qwen3:4b-instruct for Ollama, gpt-6-luna for OpenAI")
    parser.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high"], default="none")
    parser.add_argument("--ollama-url", default=defaults.base_url)
    parser.add_argument("--timeout", type=float, default=defaults.timeout_seconds)
    parser.add_argument("--num-ctx", type=int, default=defaults.num_ctx)
    parser.add_argument("--max-output-tokens", type=int, default=defaults.max_output_tokens)


def llm_config(args: argparse.Namespace) -> LLMConfig:
    model = args.model or ("gpt-6-luna" if args.provider == "openai" else "qwen3:4b-instruct")
    return LLMConfig(provider=args.provider, model=model, base_url=args.ollama_url,
                     timeout_seconds=args.timeout, reasoning_effort=args.reasoning_effort,
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
        assistant = PortfolioAssistant(create_client(config), config, mode=args.mode,
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
        if "usage" in result.metrics:
            print("OpenAI usage: " + json.dumps(result.metrics["usage"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
