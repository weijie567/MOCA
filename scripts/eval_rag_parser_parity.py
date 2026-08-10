"""Run parser-only format parity through the production ParserRegistry boundary."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from src.rag.evaluation.contracts import FormatParityContractError, load_format_parity_contract
from src.rag.evaluation.parser_parity import ParserParityRunV1, evaluate_parser_parity
from src.rag.parsers.registry import ParserRegistry


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPOSITORY_ROOT / "evaluation/rag_sources/format_parity_manifest.jsonl"
DEFAULT_GOLD = REPOSITORY_ROOT / "evaluation/golden/rag_format_parity_gold.json"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "evaluation/reports/rag_parser_parity.json"
DEFAULT_MODE = "parser_direct"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the exact format-parity corpus through ParserRegistry without persistence."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--generated-at",
        help="Injected ISO-8601 timestamp for reproducible output (defaults to current UTC time).",
    )
    return parser


def run_parser_parity(
    *,
    manifest_path: Path,
    gold_path: Path,
    output_path: Path,
    generated_at: str,
    parser_registry: ParserRegistry | None = None,
) -> ParserParityRunV1:
    """Validate inputs, parse all nine fixtures, and write canonical sorted JSON."""

    dataset = load_format_parity_contract(
        manifest_path,
        gold_path,
        repository_root=REPOSITORY_ROOT,
    )
    result = evaluate_parser_parity(
        dataset,
        parser_registry=parser_registry,
        generated_at=generated_at,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    generated_at = args.generated_at or datetime.now(UTC).isoformat()
    try:
        result = run_parser_parity(
            manifest_path=args.manifest,
            gold_path=args.gold,
            output_path=args.output,
            generated_at=generated_at,
        )
    except FormatParityContractError as exc:
        parser.error(f"format parity contract rejected: {exc.reason_code}")

    print(f"Parser parity: outcome={result.outcome.value} mode={result.mode} variants={len(result.variant_results)}")
    return 0 if result.outcome.value == "completed_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
