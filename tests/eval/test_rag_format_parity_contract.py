from __future__ import annotations

import hashlib
import inspect
import json
import shutil
import time
import tomllib
from copy import deepcopy
from pathlib import Path

import pdfplumber
import pypdfium2
import pytest
from PIL import ImageChops, ImageStat

from evaluation.rag_sources.build_fixtures import (
    FixtureBuildError,
    build_fixture_family,
)

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


def _generator_identity(*, profile: str = "test-profile") -> dict[str, object]:
    return {
        "schema_version": "rag_format_parity_fixture_generator.v1",
        "builder_sha256": "1" * 64,
        "profile": profile,
        "reportlab_version": "5.0.0",
        "pillow_version": "12.2.0",
        "pypdfium2_version": "5.10.1",
        "pdfplumber_version": "0.11.10",
        "cjk_font_sha256": "2" * 64,
        "raster_dpi": 200,
        "deterministic_metadata_profile": "moca-pdf-invariant-v1",
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
                "generator_identity": _generator_identity(),
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


def test_checked_in_format_parity_contract_is_valid() -> None:
    records = _read_manifest(CHECKED_IN_MANIFEST)
    matching_fixture_count = 0
    for record in records:
        for variant in record["variants"]:
            fixture_path = REPOSITORY_ROOT / variant["path"]
            actual_hash = _sha256(fixture_path)
            assert actual_hash == variant["sha256"]
            matching_fixture_count += 1

    dataset = load_format_parity_contract(CHECKED_IN_MANIFEST, CHECKED_IN_GOLD, repository_root=REPOSITORY_ROOT)
    assert matching_fixture_count == 9
    assert len(dataset.policies) == 3
    assert len(dataset.fixture_hashes) == 9
    assert len(dataset.baseline_identity) == 64


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


def test_reportlab_is_locked_to_exact_required_version() -> None:
    project = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "reportlab==5.0.0" in project["project"]["dependencies"]
    lock = (REPOSITORY_ROOT / "uv.lock").read_text(encoding="utf-8")
    assert 'name = "reportlab"\nversion = "5.0.0"' in lock


def _built_family_hashes(root: Path) -> dict[str, str]:
    paths = sorted((root / "evaluation/rag_sources/fixtures").glob("*/*"))
    paths.append(root / "evaluation/rag_sources/format_parity_manifest.jsonl")
    return {path.relative_to(root).as_posix(): _sha256(path) for path in paths if path.is_file()}


def test_fixture_builder_is_byte_deterministic_across_wall_clock_gap(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first = build_fixture_family(repository_root=REPOSITORY_ROOT, output_root=first_root)
    first_hashes = _built_family_hashes(first_root)
    time.sleep(1.1)
    second = build_fixture_family(repository_root=REPOSITORY_ROOT, output_root=second_root)
    second_hashes = _built_family_hashes(second_root)

    assert first_hashes == second_hashes
    assert len(first_hashes) == 10  # three Markdown + six PDFs + complete manifest
    assert first.generator_identity == second.generator_identity
    assert first.manifest_hash == second.manifest_hash
    assert len({record["generator_identity_hash"] for record in _read_manifest(first.manifest_path)}) == 1


def test_changed_generator_identity_prevents_reuse(tmp_path: Path) -> None:
    first = build_fixture_family(repository_root=REPOSITORY_ROOT, output_root=tmp_path / "first")

    with pytest.raises(FixtureBuildError, match="generator_identity_mismatch") as exc_info:
        build_fixture_family(
            repository_root=REPOSITORY_ROOT,
            output_root=tmp_path / "changed",
            generator_profile="changed-profile",
            expected_generator_identity=first.generator_identity,
        )

    assert exc_info.value.reason_code == "generator_identity_mismatch"
    assert not (tmp_path / "changed/evaluation/rag_sources/format_parity_manifest.jsonl").exists()


def _normalized(text: str) -> str:
    return "".join(text.split())


def _render_page(document: pypdfium2.PdfDocument, page_index: int):
    page = document[page_index]
    try:
        return page.render(scale=1).to_pil().convert("L")
    finally:
        close_page = getattr(page, "close", None)
        if callable(close_page):
            close_page()


def test_checked_in_pdfs_preserve_five_page_semantic_order_and_scan_pixels() -> None:
    dataset = load_format_parity_contract(CHECKED_IN_MANIFEST, CHECKED_IN_GOLD, repository_root=REPOSITORY_ROOT)

    for policy in dataset.policies:
        variants = {variant.format: variant for variant in policy.variants}
        digital_path = REPOSITORY_ROOT / variants["digital_pdf"].path
        scanned_path = REPOSITORY_ROOT / variants["scanned_pdf"].path
        with pdfplumber.open(digital_path) as digital:
            assert len(digital.pages) == 5
            digital_text = _normalized("\n".join(page.extract_text() or "" for page in digital.pages))
        with pdfplumber.open(scanned_path) as scanned:
            assert len(scanned.pages) == 5
            assert sum(len(page.extract_text() or "") for page in scanned.pages) == 0

        positions = [digital_text.index(_normalized(anchor.text)) for anchor in policy.gold.anchors]
        assert positions == sorted(positions)
        assert any(anchor.kind == "table_header" for anchor in policy.gold.anchors)
        assert any(anchor.kind == "table_row" for anchor in policy.gold.anchors)

        digital_document = pypdfium2.PdfDocument(str(digital_path))
        scanned_document = pypdfium2.PdfDocument(str(scanned_path))
        try:
            assert len(digital_document) == len(scanned_document) == 5
            for page_index in range(5):
                digital_page = _render_page(digital_document, page_index)
                scanned_page = _render_page(scanned_document, page_index)
                assert digital_page.size == scanned_page.size
                difference = ImageChops.difference(digital_page, scanned_page)
                assert ImageStat.Stat(difference).mean[0] < 3.0
        finally:
            digital_document.close()
            scanned_document.close()


def test_semantic_gold_has_stable_shared_truth_and_no_chunk_binding() -> None:
    raw = json.loads(CHECKED_IN_GOLD.read_text(encoding="utf-8"))
    serialized = json.dumps(raw, ensure_ascii=False)
    assert "expected_chunk_id" not in serialized
    assert "format_answers" not in serialized

    dataset = load_format_parity_contract(CHECKED_IN_MANIFEST, CHECKED_IN_GOLD, repository_root=REPOSITORY_ROOT)
    case_ids: set[str] = set()
    anchor_ids: set[str] = set()
    categories: set[str] = set()
    for policy in dataset.policies:
        assert 8 <= len(policy.gold.anchors) <= 12
        assert 6 <= len(policy.gold.cases) <= 8
        local_anchors = {anchor.anchor_id for anchor in policy.gold.anchors}
        assert not anchor_ids.intersection(local_anchors)
        anchor_ids.update(local_anchors)
        for case in policy.gold.cases:
            assert case.case_id not in case_ids
            case_ids.add(case.case_id)
            categories.add(case.category)
            assert set(case.evidence_anchor_ids).issubset(local_anchors)
    assert categories == {
        "facts",
        "exceptions",
        "amounts_time_limits",
        "tables",
        "cross_section",
        "no_answer",
    }


@pytest.mark.parametrize("forbidden_key", ["expected_chunk_id", "expected_chunk_ids", "format_answers"])
def test_gold_rejects_chunk_bound_or_format_specific_truth(tmp_path: Path, forbidden_key: str) -> None:
    manifest_path, gold_path, _ = _make_valid_contract(tmp_path)
    raw = json.loads(gold_path.read_text(encoding="utf-8"))
    raw["policies"][0]["cases"][0][forbidden_key] = ["forbidden"]
    gold_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(FormatParityContractError, match="gold_(chunk_binding_forbidden|schema_invalid)"):
        load_format_parity_contract(manifest_path, gold_path, repository_root=tmp_path)


def test_manifest_gold_and_fixture_hashes_are_independent_reuse_inputs(tmp_path: Path) -> None:
    shutil.copytree(REPOSITORY_ROOT / "evaluation/rag_sources", tmp_path / "evaluation/rag_sources")
    shutil.copytree(REPOSITORY_ROOT / "evaluation/golden", tmp_path / "evaluation/golden")
    manifest_path = tmp_path / "evaluation/rag_sources/format_parity_manifest.jsonl"
    gold_path = tmp_path / "evaluation/golden/rag_format_parity_gold.json"
    original = load_format_parity_contract(manifest_path, gold_path, repository_root=tmp_path)

    manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")
    manifest_changed = load_format_parity_contract(manifest_path, gold_path, repository_root=tmp_path)
    assert manifest_changed.manifest_hash != original.manifest_hash
    assert manifest_changed.gold_hash == original.gold_hash
    assert manifest_changed.fixture_hashes == original.fixture_hashes
    assert manifest_changed.baseline_identity != original.baseline_identity

    gold_path.write_bytes(gold_path.read_bytes() + b" \n")
    gold_changed = load_format_parity_contract(manifest_path, gold_path, repository_root=tmp_path)
    assert gold_changed.gold_hash != manifest_changed.gold_hash
    assert gold_changed.manifest_hash == manifest_changed.manifest_hash
    assert gold_changed.fixture_hashes == manifest_changed.fixture_hashes
    assert gold_changed.baseline_identity != manifest_changed.baseline_identity

    fixture_path = tmp_path / next(iter(original.fixture_hashes))
    fixture_path.write_bytes(fixture_path.read_bytes() + b"tampered")
    with pytest.raises(FormatParityContractError, match="fixture_checksum_mismatch"):
        load_format_parity_contract(manifest_path, gold_path, repository_root=tmp_path)
