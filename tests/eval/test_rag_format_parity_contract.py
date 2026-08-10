from __future__ import annotations

import hashlib
import inspect
import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.rag.evaluation.contracts import (
    FORMAT_PARITY_DOC_KEYS,
    FORMAT_VARIANTS,
    EvaluationOutcome,
    FormatParityContractError,
    load_format_parity_contract,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CHECKED_IN_MANIFEST = REPOSITORY_ROOT / "evaluation/rag_sources/format_parity_manifest.jsonl"
CHECKED_IN_GOLD = REPOSITORY_ROOT / "evaluation/golden/rag_format_parity_gold.json"

EXPECTED_STALE_MARKDOWN_HASHES = {
    "eval_refund_eligibility_and_return": (
        "b59685b3f1594906284c362b5af4ab8b3df8132a9bed6a158245406723dfee99",
        "81654bb2e4adbc7b95b41823c90d77754785c4243d60fed2b382ec7fae9ce8c7",
    ),
    "eval_quality_compensation_and_approval": (
        "e7fb86822ea99f96139b89d3a14f498588fba69e4625b8d374f9f02db4c8eb5e",
        "f7c115028dcd20da2c7e0b0033612b4bf5857c006408131b3a1bf63f5eb96cea",
    ),
    "eval_cross_border_and_digital_goods": (
        "c4bd19adcc696104fd56a1531da1f3b31d1b301f6f9fb0c471374f2d19fe0c83",
        "8641827819922c734f3baebc913b009c70e41fe37ca551380e24cebcf19e5cb9",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_manifest(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_manifest(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _gold_policy(doc_key: str, index: int) -> dict[str, object]:
    prefix = f"p{index}"
    categories = (
        "facts",
        "exceptions",
        "amounts_time_limits",
        "tables",
        "cross_section",
        "no_answer",
    )
    return {
        "policy_id": doc_key,
        "title": f"Policy {index}",
        "anchors": [
            {
                "anchor_id": f"{prefix}-anchor-{anchor_index}",
                "kind": "fact",
                "section": f"Section {anchor_index}",
                "text": f"Protected semantic fact {index}-{anchor_index}",
            }
            for anchor_index in range(1, 9)
        ],
        "cases": [
            {
                "case_id": f"{prefix}-case-{case_index}",
                "category": category,
                "question": f"Question {index}-{case_index}",
                "expected_section": None if category == "no_answer" else f"Section {case_index}",
                "evidence_anchor_ids": [] if category == "no_answer" else [f"{prefix}-anchor-{case_index}"],
                "expected_answer": None if category == "no_answer" else f"Answer {index}-{case_index}",
                "no_answer": category == "no_answer",
            }
            for case_index, category in enumerate(categories, start=1)
        ],
    }


def _make_valid_contract(tmp_path: Path) -> tuple[Path, Path, list[dict[str, object]]]:
    records: list[dict[str, object]] = []
    for index, doc_key in enumerate(FORMAT_PARITY_DOC_KEYS, start=1):
        directory_name = doc_key.removeprefix("eval_")
        directory = tmp_path / "evaluation/rag_sources/fixtures" / directory_name
        directory.mkdir(parents=True)
        markdown = directory / f"{directory_name}.md"
        digital = directory / f"{directory_name}.digital.pdf"
        scanned = directory / f"{directory_name}.scanned.pdf"
        markdown.write_text(f"# Policy {index}\n\nCanonical policy content {index}.\n", encoding="utf-8")
        digital.write_bytes(f"digital-pdf-{index}".encode())
        scanned.write_bytes(f"scanned-pdf-{index}".encode())
        relative_markdown = markdown.relative_to(tmp_path).as_posix()
        records.append(
            {
                "doc_key": doc_key,
                "parity_group": doc_key,
                "source_of_truth": relative_markdown,
                "title": f"Policy {index}",
                "variants": [
                    {
                        "extractable_text_chars": len(markdown.read_text(encoding="utf-8")),
                        "format": "markdown",
                        "pages": None,
                        "path": relative_markdown,
                        "sha256": _sha256(markdown),
                        "source_type": "policy_markdown",
                    },
                    {
                        "extractable_text_chars": 1200,
                        "format": "digital_pdf",
                        "pages": 5,
                        "path": digital.relative_to(tmp_path).as_posix(),
                        "sha256": _sha256(digital),
                        "source_type": "policy_pdf",
                    },
                    {
                        "extractable_text_chars": 0,
                        "format": "scanned_pdf",
                        "pages": 5,
                        "path": scanned.relative_to(tmp_path).as_posix(),
                        "sha256": _sha256(scanned),
                        "source_type": "policy_pdf",
                    },
                ],
            }
        )

    manifest_path = tmp_path / "evaluation/rag_sources/format_parity_manifest.jsonl"
    gold_path = tmp_path / "evaluation/golden/rag_format_parity_gold.json"
    _write_manifest(manifest_path, records)
    gold_path.parent.mkdir(parents=True)
    gold_path.write_text(
        json.dumps(
            {
                "schema_version": "rag_format_parity_gold.v1",
                "policies": [
                    _gold_policy(doc_key, index) for index, doc_key in enumerate(FORMAT_PARITY_DOC_KEYS, start=1)
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path, gold_path, records


def _load_temp_contract(tmp_path: Path, records: list[dict[str, object]]):
    manifest_path = tmp_path / "evaluation/rag_sources/format_parity_manifest.jsonl"
    gold_path = tmp_path / "evaluation/golden/rag_format_parity_gold.json"
    _write_manifest(manifest_path, records)
    return load_format_parity_contract(manifest_path, gold_path, repository_root=tmp_path)


def test_contract_constants_and_outcome_vocabulary_are_exact() -> None:
    assert FORMAT_PARITY_DOC_KEYS == (
        "eval_refund_eligibility_and_return",
        "eval_quality_compensation_and_approval",
        "eval_cross_border_and_digital_goods",
    )
    assert FORMAT_VARIANTS == (
        ("markdown", "policy_markdown"),
        ("digital_pdf", "policy_pdf"),
        ("scanned_pdf", "policy_pdf"),
    )
    assert {outcome.value for outcome in EvaluationOutcome} == {
        "completed_pass",
        "completed_quality_fail",
        "unavailable_prerequisite",
        "execution_error",
    }


def test_valid_contract_returns_exact_3_groups_and_9_variants(tmp_path: Path) -> None:
    manifest_path, gold_path, _ = _make_valid_contract(tmp_path)

    dataset = load_format_parity_contract(manifest_path, gold_path, repository_root=tmp_path)

    assert len(dataset.policies) == 3
    assert sum(len(policy.variants) for policy in dataset.policies) == 9
    assert set(dataset.fixture_hashes) == {
        variant.path for policy in dataset.policies for variant in policy.variants
    }
    assert len(dataset.manifest_hash) == len(dataset.gold_hash) == 64


def test_checked_in_manifest_exposes_three_markdown_mismatches_and_six_matching_pdfs() -> None:
    records = _read_manifest(CHECKED_IN_MANIFEST)
    actual_markdown: dict[str, tuple[str, str]] = {}
    matching_pdf_count = 0
    for record in records:
        doc_key = str(record["doc_key"])
        for variant in record["variants"]:
            fixture_path = REPOSITORY_ROOT / variant["path"]
            actual_hash = _sha256(fixture_path)
            if variant["format"] == "markdown":
                actual_markdown[doc_key] = (variant["sha256"], actual_hash)
            else:
                assert actual_hash == variant["sha256"]
                matching_pdf_count += 1

    assert actual_markdown == EXPECTED_STALE_MARKDOWN_HASHES
    assert matching_pdf_count == 6
    with pytest.raises(FormatParityContractError, match="fixture_checksum_mismatch") as exc_info:
        load_format_parity_contract(CHECKED_IN_MANIFEST, CHECKED_IN_GOLD, repository_root=REPOSITORY_ROOT)
    assert exc_info.value.reason_code == "fixture_checksum_mismatch"


def test_duplicate_missing_and_extra_groups_fail_closed(tmp_path: Path) -> None:
    _, _, records = _make_valid_contract(tmp_path)

    with pytest.raises(FormatParityContractError, match="duplicate_manifest_group"):
        _load_temp_contract(tmp_path, [*records, deepcopy(records[0])])
    with pytest.raises(FormatParityContractError, match="manifest_group_set_invalid"):
        _load_temp_contract(tmp_path, records[:-1])

    extra = deepcopy(records[0])
    extra["doc_key"] = extra["parity_group"] = "eval_unapproved_policy"
    with pytest.raises(FormatParityContractError, match="manifest_group_set_invalid"):
        _load_temp_contract(tmp_path, [*records, extra])


@pytest.mark.parametrize(
    ("mutation", "reason_code"),
    [
        (lambda records: records[0].update(parity_group="eval_wrong"), "parity_group_mismatch"),
        (
            lambda records: records[0].update(source_of_truth=records[0]["variants"][1]["path"]),
            "source_of_truth_mismatch",
        ),
        (lambda records: records[0]["variants"].pop(), "manifest_schema_invalid"),
        (
            lambda records: records[0]["variants"][0].update(source_type="policy_pdf"),
            "manifest_variant_set_invalid",
        ),
        (lambda records: records[0]["variants"][0].update(pages=1), "variant_metadata_invalid"),
        (lambda records: records[0]["variants"][1].update(pages=0), "variant_metadata_invalid"),
        (
            lambda records: records[0]["variants"][1].update(extractable_text_chars=0),
            "variant_metadata_invalid",
        ),
        (
            lambda records: records[0]["variants"][2].update(extractable_text_chars=1),
            "variant_metadata_invalid",
        ),
        (lambda records: records[0]["variants"][0].update(sha256="bad"), "manifest_schema_invalid"),
        (lambda records: records[0]["variants"][0].update(sha256="0" * 64), "fixture_checksum_mismatch"),
    ],
)
def test_manifest_shape_metadata_source_and_checksum_fail_closed(
    tmp_path: Path,
    mutation,
    reason_code: str,
) -> None:
    _, _, original = _make_valid_contract(tmp_path)
    records = deepcopy(original)
    mutation(records)

    with pytest.raises(FormatParityContractError, match=reason_code) as exc_info:
        _load_temp_contract(tmp_path, records)
    assert exc_info.value.reason_code == reason_code


@pytest.mark.parametrize("bad_path", ["../escape.md", "/tmp/absolute.md"])
def test_absolute_and_parent_escaping_fixture_paths_fail_closed(tmp_path: Path, bad_path: str) -> None:
    _, _, original = _make_valid_contract(tmp_path)
    records = deepcopy(original)
    records[0]["variants"][0]["path"] = bad_path
    records[0]["source_of_truth"] = bad_path

    with pytest.raises(FormatParityContractError, match="fixture_path_invalid"):
        _load_temp_contract(tmp_path, records)


def test_symlink_escaping_fixture_root_fails_closed(tmp_path: Path) -> None:
    _, _, original = _make_valid_contract(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    escaped = tmp_path / "evaluation/rag_sources/fixtures/refund_eligibility_and_return/escaped.md"
    escaped.symlink_to(outside)
    records = deepcopy(original)
    relative = escaped.relative_to(tmp_path).as_posix()
    records[0]["variants"][0].update(path=relative, sha256=_sha256(outside))
    records[0]["source_of_truth"] = relative

    with pytest.raises(FormatParityContractError, match="fixture_path_invalid"):
        _load_temp_contract(tmp_path, records)


def test_tampered_fixture_bytes_fail_closed(tmp_path: Path) -> None:
    manifest_path, gold_path, records = _make_valid_contract(tmp_path)
    digital_path = tmp_path / records[1]["variants"][1]["path"]
    digital_path.write_bytes(b"tampered")

    with pytest.raises(FormatParityContractError, match="fixture_checksum_mismatch"):
        load_format_parity_contract(manifest_path, gold_path, repository_root=tmp_path)


def test_loader_exposes_no_validation_bypass() -> None:
    assert tuple(inspect.signature(load_format_parity_contract).parameters) == (
        "manifest_path",
        "gold_path",
        "repository_root",
    )
