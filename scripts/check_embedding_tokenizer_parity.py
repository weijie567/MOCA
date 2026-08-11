from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse
from uuid import UUID, uuid4

from src.config import settings
from src.rag.embedder import EmbeddingService, EmbeddingUsageStatus
from src.rag.embedding_tokenizer import ProviderParityStatus, load_embedding_tokenizer_config
from src.rag.parsers.base import BlockType, ParsedBlock
from src.rag.policy_embedding_input import PolicyEmbeddingInputAssembler
from src.rag.tokenizer_parity import (
    ParityProbeResultV1,
    build_parity_report,
    parity_content_sha256,
    write_parity_report_create_only,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROBES = ROOT / "evaluation" / "golden" / "embedding_tokenizer_parity_probes.v1.json"
DEFAULT_REPORT_ROOT = ROOT / "evaluation" / "reports" / "rag_embedding_tokenizer" / "v1"


@dataclass(frozen=True, slots=True)
class _AssembledProbe:
    probe_id: str
    category: str
    embedding_input: str
    embedding_input_sha256: str
    offline_tokens: int


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check immutable provider tokenizer parity.")
    parser.add_argument("--probe-fixture", type=Path, default=DEFAULT_PROBES)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--run-id", type=UUID, default=None)
    return parser.parse_args()


def _load_assembled_probes(
    fixture_path: Path,
    *,
    assembler: PolicyEmbeddingInputAssembler,
) -> tuple[_AssembledProbe, ...]:
    payload = json.loads(fixture_path.read_bytes())
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "note", "probes"}:
        raise RuntimeError("parity_probe_fixture_invalid")
    if payload["schema_version"] != "embedding_tokenizer_parity_probes.v1":
        raise RuntimeError("parity_probe_fixture_invalid")
    raw_probes = payload["probes"]
    if not isinstance(raw_probes, list) or len(raw_probes) != 10:
        raise RuntimeError("parity_probe_fixture_invalid")

    assembled_probes: list[_AssembledProbe] = []
    for index, raw_probe in enumerate(raw_probes):
        if not isinstance(raw_probe, dict) or set(raw_probe) != {
            "id",
            "category",
            "doc_key",
            "title",
            "block",
        }:
            raise RuntimeError("parity_probe_fixture_invalid")
        block_payload = raw_probe["block"]
        if not isinstance(block_payload, dict) or set(block_payload) != {
            "source_block_id",
            "block_type",
            "content",
        }:
            raise RuntimeError("parity_probe_fixture_invalid")
        probe_id = _required_string(raw_probe["id"])
        category = _required_string(raw_probe["category"])
        doc_key = _required_string(raw_probe["doc_key"])
        title = _required_string(raw_probe["title"])
        source_block_id = _required_string(block_payload["source_block_id"])
        block_type = _required_string(block_payload["block_type"])
        content = _required_string(block_payload["content"])
        if block_type not in {
            "heading",
            "paragraph",
            "table",
            "image",
            "list",
            "footer",
            "header",
            "ocr_text",
        }:
            raise RuntimeError("parity_probe_fixture_invalid")
        block = ParsedBlock(
            source_block_id=source_block_id,
            block_index=index,
            block_type=cast(BlockType, block_type),
            text=content,
            normalized_text=content,
            source_type="parity_safe_synthetic",
            parser_name="parity_fixture",
            parser_version="embedding_tokenizer_parity_probes.v1",
            page_number=None,
            box=None,
        )
        assembled = assembler.assemble(blocks=(block,), doc_key=doc_key, title=title)
        if len(assembled) != 1:
            raise RuntimeError("parity_probe_fixture_invalid")
        final_input = assembled[0]
        assembled_probes.append(
            _AssembledProbe(
                probe_id=probe_id,
                category=category,
                embedding_input=final_input.embedding_input,
                embedding_input_sha256=final_input.embedding_input_hash,
                offline_tokens=final_input.embedding_token_count,
            )
        )
    if len({probe.probe_id for probe in assembled_probes}) != 10:
        raise RuntimeError("parity_probe_fixture_invalid")
    return tuple(assembled_probes)


async def _provider_observations(
    probes: tuple[_AssembledProbe, ...],
) -> tuple[tuple[ParityProbeResultV1, ...], int | None, int | None, str | None]:
    if not (settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY")):
        return _without_provider_counts(probes), None, None, "provider_credentials_unavailable"

    service = EmbeddingService(batch_size=10)
    observations: list[ParityProbeResultV1] = []
    try:
        for probe in probes:
            result = await service.embed_documents_with_usage([probe.embedding_input])
            usage = result.request_usages[0]
            prompt_tokens = usage.prompt_tokens if usage.status is EmbeddingUsageStatus.REPORTED else None
            total_tokens = usage.total_tokens if usage.status is EmbeddingUsageStatus.REPORTED else None
            observations.append(
                _observation(
                    probe,
                    provider_prompt_tokens=prompt_tokens,
                    provider_total_tokens=total_tokens,
                )
            )
        aggregate = await service.embed_documents_with_usage([probe.embedding_input for probe in probes])
    except Exception:
        return _without_provider_counts(probes), None, None, "provider_request_unavailable"

    unavailable_reason = (
        "provider_usage_unavailable"
        if any(observation.provider_prompt_tokens is None for observation in observations)
        or aggregate.usage_status is EmbeddingUsageStatus.UNAVAILABLE
        else None
    )
    return tuple(observations), aggregate.prompt_tokens, aggregate.total_tokens, unavailable_reason


def _without_provider_counts(probes: tuple[_AssembledProbe, ...]) -> tuple[ParityProbeResultV1, ...]:
    return tuple(_observation(probe, provider_prompt_tokens=None, provider_total_tokens=None) for probe in probes)


def _observation(
    probe: _AssembledProbe,
    *,
    provider_prompt_tokens: int | None,
    provider_total_tokens: int | None,
) -> ParityProbeResultV1:
    exact_match = (
        None
        if provider_prompt_tokens is None or provider_total_tokens is None
        else provider_prompt_tokens == probe.offline_tokens
    )
    return ParityProbeResultV1(
        probe_id=probe.probe_id,
        category=probe.category,
        embedding_input_sha256=probe.embedding_input_sha256,
        offline_tokens=probe.offline_tokens,
        provider_prompt_tokens=provider_prompt_tokens,
        provider_total_tokens=provider_total_tokens,
        exact_match=exact_match,
    )


async def _run(args: argparse.Namespace) -> int:
    config = load_embedding_tokenizer_config()
    assembler = PolicyEmbeddingInputAssembler()
    probes = _load_assembled_probes(args.probe_fixture, assembler=assembler)
    observations, aggregate_prompt, aggregate_total, unavailable_reason = await _provider_observations(probes)
    report = build_parity_report(
        run_id=args.run_id or uuid4(),
        captured_at=datetime.now(UTC),
        region_class=_region_class(settings.embedding_base_url),
        config=config,
        probe_fixture_sha256="sha256:" + hashlib.sha256(args.probe_fixture.read_bytes()).hexdigest(),
        submitted_content_sha256=parity_content_sha256(observations),
        probes=observations,
        aggregate_provider_prompt_tokens=aggregate_prompt,
        aggregate_provider_total_tokens=aggregate_total,
        unavailable_reason=unavailable_reason,
    )
    report_path = write_parity_report_create_only(report, root=args.output_root)
    safe_output: dict[str, Any] = {
        "schema_version": report.schema_version,
        "run_id": str(report.run_id),
        "provider_parity_status": report.provider_parity_status.value,
        "reason_code": report.reason_code,
        "report_sha256": "sha256:" + hashlib.sha256(report_path.read_bytes()).hexdigest(),
    }
    print(json.dumps(safe_output, sort_keys=True, separators=(",", ":")))
    return 0 if report.provider_parity_status is ProviderParityStatus.PASSED else 2


def _region_class(base_url: str) -> str:
    hostname = (urlparse(base_url).hostname or "").lower()
    return "dashscope_public" if hostname == "dashscope.aliyuncs.com" else "custom_openai_compatible"


def _required_string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("parity_probe_fixture_invalid")
    return value


def main() -> int:
    try:
        return asyncio.run(_run(_parse_args()))
    except Exception:
        print('{"error":"parity_execution_failed"}')
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
