from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

from src.config import Settings


ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = ROOT / "src" / "rag" / "assets"
TOKENIZER_ROOT = ASSET_ROOT / "qwen3_embedding_0_6b"
CONTRACT_PATH = ASSET_ROOT / "embedding_tokenizer.v1.json"
TOKENIZER_PATH = TOKENIZER_ROOT / "tokenizer.json"
SOURCE_PATH = TOKENIZER_ROOT / "SOURCE.json"
LICENSE_PATH = TOKENIZER_ROOT / "LICENSE"
PROBES_PATH = ROOT / "evaluation" / "golden" / "embedding_tokenizer_count_probes.v1.json"

TOKENIZER_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
TOKENIZER_SHA256 = "def76fb086971c7867b829c23a26261e38d9d74e02139253b38aeb9df8b4b50a"
TOKENIZER_SIZE_BYTES = 11_423_705


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_freezes_the_approved_embedding_tokenizer_configuration() -> None:
    contract = _load_json(CONTRACT_PATH)

    assert contract == {
        "schema_version": "embedding_tokenizer.v1",
        "provider": "dashscope",
        "model": "text-embedding-v4",
        "dimensions": 1024,
        "tokenizer_source": "Qwen/Qwen3-Embedding-0.6B",
        "tokenizer_revision": TOKENIZER_REVISION,
        "tokenizer_asset_path": "qwen3_embedding_0_6b/tokenizer.json",
        "tokenizer_asset_sha256": TOKENIZER_SHA256,
        "tokenizer_asset_size_bytes": TOKENIZER_SIZE_BYTES,
        "tokenizer_runtime": "tokenizers==0.23.1",
        "normalization": "tokenizer_asset_defined",
        "add_special_tokens": True,
        "eos_token": "<|endoftext|>",
        "eos_token_id": 151643,
        "provider_max_input_tokens": 8192,
        "provider_max_batch_inputs": 10,
        "max_embedding_tokens": 512,
        "target_embedding_tokens": 384,
        "overlap_tokens": 48,
        "assembly_schema_version": "policy_embedding_input.v1",
        "mapping_assurance": "empirically_provider_parity_approved_not_vendor_guaranteed",
    }
    canonical = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == "925446ea470da4da9a0ac9aee81f9103bb4b07bd7292c761bd98a36edd749584"


def test_vendored_asset_and_provenance_are_exact_and_offline() -> None:
    tokenizer_bytes = TOKENIZER_PATH.read_bytes()
    source = _load_json(SOURCE_PATH)
    tokenizer_payload = json.loads(tokenizer_bytes)

    assert len(tokenizer_bytes) == TOKENIZER_SIZE_BYTES
    assert hashlib.sha256(tokenizer_bytes).hexdigest() == TOKENIZER_SHA256
    assert tokenizer_payload["model"]["type"] == "BPE"
    assert tokenizer_payload["post_processor"]["type"] == "Sequence"
    assert source["source_repository"] == "Qwen/Qwen3-Embedding-0.6B"
    assert source["source_revision"] == TOKENIZER_REVISION
    assert source["tokenizer_asset_sha256"] == TOKENIZER_SHA256
    assert source["tokenizer_asset_size_bytes"] == TOKENIZER_SIZE_BYTES
    assert source["license"] == "Apache-2.0"
    assert source["provider_mapping"] == "empirical_not_vendor_guaranteed"
    assert "Apache License" in LICENSE_PATH.read_text(encoding="utf-8")
    assert "Version 2.0, January 2004" in LICENSE_PATH.read_text(encoding="utf-8")


def test_tokenizers_dependency_is_exact_and_locked_for_dev_and_ci_platforms() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))

    assert "tokenizers==0.23.1" in project["project"]["dependencies"]
    package = next(item for item in lock["package"] if item["name"] == "tokenizers")
    assert package["version"] == "0.23.1"
    assert package["sdist"]["hash"].startswith("sha256:")
    assert len(package["sdist"]["hash"]) == len("sha256:") + 64
    wheel_urls = [wheel["url"] for wheel in package["wheels"]]
    assert any("cp310-abi3-macosx_11_0_arm64.whl" in url for url in wheel_urls)
    assert any("cp310-abi3-manylinux_2_17_x86_64" in url for url in wheel_urls)
    assert all(wheel["hash"].startswith("sha256:") for wheel in package["wheels"])


def test_settings_select_only_the_versioned_contract() -> None:
    settings = Settings()

    assert settings.embedding_model == "text-embedding-v4"
    assert settings.embedding_dimensions == 1024
    assert settings.embedding_batch_size == 10
    assert settings.embedding_tokenizer_contract_version == "embedding_tokenizer.v1"


def test_offline_probe_fixture_is_safe_complete_and_not_live_parity_evidence() -> None:
    fixture = _load_json(PROBES_PATH)

    assert fixture["schema_version"] == "embedding_tokenizer_count_probes.v1"
    assert fixture["tokenizer_contract_version"] == "embedding_tokenizer.v1"
    probes = fixture["probes"]
    assert {probe["category"] for probe in probes} == {
        "ascii",
        "chinese",
        "mixed",
        "markdown_table",
        "url",
        "numbers",
        "emoji",
        "unpunctuated_zh",
        "combining_unicode",
        "whitespace_envelope",
    }
    assert all(probe["expected_tokens"] == probe["expected_tokens_without_special"] + 1 for probe in probes)
    serialized = json.dumps(fixture, ensure_ascii=False).lower()
    for forbidden in ("api_key", "credential", "request_id", "provider_response", "parity_status"):
        assert forbidden not in serialized
