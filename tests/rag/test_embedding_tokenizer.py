from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from tokenizers import Tokenizer

from src.config import Settings
from src.rag.embedding_tokenizer import (
    EmbeddingTokenCounter,
    EmbeddingTokenizerError,
    EmbeddingTokenizerFailureCode,
    ProviderParityStatus,
    load_embedding_tokenizer_config,
)


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


def test_config_loader_returns_a_frozen_typed_config_and_canonical_fingerprint() -> None:
    config = load_embedding_tokenizer_config()

    assert config.schema_version == "embedding_tokenizer.v1"
    assert config.model == "text-embedding-v4"
    assert config.config_fingerprint == "sha256:925446ea470da4da9a0ac9aee81f9103bb4b07bd7292c761bd98a36edd749584"
    with pytest.raises(FrozenInstanceError):
        config.model = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "failure_code"),
    [
        ("schema_version", "embedding_tokenizer.v2", EmbeddingTokenizerFailureCode.UNKNOWN_CONTRACT),
        ("model", "unknown-embedding-model", EmbeddingTokenizerFailureCode.UNSUPPORTED_CONTRACT),
        ("unexpected", True, EmbeddingTokenizerFailureCode.CONFIG_INVALID),
    ],
)
def test_config_loader_fails_closed_on_unknown_or_ambiguous_contracts(
    tmp_path: Path,
    field: str,
    value: object,
    failure_code: EmbeddingTokenizerFailureCode,
) -> None:
    payload = _load_json(CONTRACT_PATH)
    payload[field] = value
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EmbeddingTokenizerError) as exc_info:
        load_embedding_tokenizer_config(contract_path)

    assert exc_info.value.code is failure_code
    assert str(exc_info.value) == failure_code.value
    assert str(tmp_path) not in str(exc_info.value)


@pytest.mark.parametrize(
    ("contract_bytes", "failure_code"),
    [
        (b"not-json", EmbeddingTokenizerFailureCode.CONFIG_INVALID),
        (b"{}", EmbeddingTokenizerFailureCode.CONFIG_INVALID),
    ],
)
def test_config_loader_never_leaks_paths_or_raw_parse_errors(
    tmp_path: Path,
    contract_bytes: bytes,
    failure_code: EmbeddingTokenizerFailureCode,
) -> None:
    contract_path = tmp_path / "private-contract.json"
    contract_path.write_bytes(contract_bytes)

    with pytest.raises(EmbeddingTokenizerError) as exc_info:
        load_embedding_tokenizer_config(contract_path)

    assert exc_info.value.code is failure_code
    assert str(exc_info.value) == failure_code.value
    assert "private-contract" not in str(exc_info.value)
    assert "json" not in str(exc_info.value)


def test_counter_matches_all_offline_golden_counts_and_eos_delta() -> None:
    counter = EmbeddingTokenCounter(load_embedding_tokenizer_config())
    raw_tokenizer = Tokenizer.from_file(str(TOKENIZER_PATH))

    for probe in _load_json(PROBES_PATH)["probes"]:
        assert counter.count(probe["text"]) == probe["expected_tokens"]
        assert (
            len(raw_tokenizer.encode(probe["text"], add_special_tokens=False).ids)
            == probe["expected_tokens_without_special"]
        )
        assert probe["expected_tokens"] - probe["expected_tokens_without_special"] == 1

    assert counter.count("") == 1


def test_counter_is_repeatable_and_uses_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr("socket.create_connection", reject_network)
    counter = EmbeddingTokenCounter(load_embedding_tokenizer_config())

    first = counter.count("退款 policy deterministic probe")
    second = counter.count("退款 policy deterministic probe")

    assert first == second
    assert first > 0


def test_counter_fails_closed_on_missing_size_or_hash_drift(tmp_path: Path) -> None:
    config = load_embedding_tokenizer_config()
    isolated = replace(config, _asset_root=tmp_path)

    with pytest.raises(EmbeddingTokenizerError) as missing:
        EmbeddingTokenCounter(isolated)
    assert missing.value.code is EmbeddingTokenizerFailureCode.ASSET_MISSING

    asset_path = tmp_path / config.tokenizer_asset_path
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"changed")
    with pytest.raises(EmbeddingTokenizerError) as wrong_size:
        EmbeddingTokenCounter(isolated)
    assert wrong_size.value.code is EmbeddingTokenizerFailureCode.ASSET_SIZE_MISMATCH

    shutil.copyfile(TOKENIZER_PATH, asset_path)
    with asset_path.open("r+b") as asset_file:
        asset_file.write(b"X")
    with pytest.raises(EmbeddingTokenizerError) as wrong_hash:
        EmbeddingTokenCounter(isolated)
    assert wrong_hash.value.code is EmbeddingTokenizerFailureCode.ASSET_HASH_MISMATCH
    assert str(tmp_path) not in str(wrong_hash.value)


def test_counter_fails_closed_on_runtime_or_tokenizer_load_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_embedding_tokenizer_config()

    monkeypatch.setattr("src.rag.embedding_tokenizer.metadata.version", lambda _: "0.0.0")
    with pytest.raises(EmbeddingTokenizerError) as runtime_error:
        EmbeddingTokenCounter(config)
    assert runtime_error.value.code is EmbeddingTokenizerFailureCode.RUNTIME_VERSION_MISMATCH

    monkeypatch.setattr("src.rag.embedding_tokenizer.metadata.version", lambda _: "0.23.1")

    class BrokenTokenizer:
        @staticmethod
        def from_file(_: str) -> None:
            raise RuntimeError("private raw tokenizer exception")

    monkeypatch.setattr("src.rag.embedding_tokenizer.Tokenizer", BrokenTokenizer)
    with pytest.raises(EmbeddingTokenizerError) as load_error:
        EmbeddingTokenCounter(config)
    assert load_error.value.code is EmbeddingTokenizerFailureCode.TOKENIZER_LOAD_FAILED
    assert str(load_error.value) == "tokenizer_load_failed"
    assert "private" not in str(load_error.value)


class _FailingTokenizer:
    def encode(self, text: str, *, add_special_tokens: bool) -> None:
        raise RuntimeError(f"private text must not leak: {text}")


class _InvalidTokenizer:
    def encode(self, text: str, *, add_special_tokens: bool) -> SimpleNamespace:
        return SimpleNamespace(ids=[])


class _NondeterministicTokenizer:
    def __init__(self) -> None:
        self.calls = 0

    def encode(self, text: str, *, add_special_tokens: bool) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(ids=[1] if self.calls % 2 else [2])


@pytest.mark.parametrize(
    ("tokenizer", "failure_code"),
    [
        (_FailingTokenizer(), EmbeddingTokenizerFailureCode.COUNT_FAILED),
        (_InvalidTokenizer(), EmbeddingTokenizerFailureCode.COUNT_INVALID),
        (_NondeterministicTokenizer(), EmbeddingTokenizerFailureCode.COUNT_NONDETERMINISTIC),
    ],
)
def test_count_failures_are_typed_deterministic_and_safe(
    tokenizer: object, failure_code: EmbeddingTokenizerFailureCode
) -> None:
    counter = EmbeddingTokenCounter(load_embedding_tokenizer_config())
    counter._tokenizer = tokenizer

    with pytest.raises(EmbeddingTokenizerError) as exc_info:
        counter.count("secret policy text")

    assert exc_info.value.code is failure_code
    assert str(exc_info.value) == failure_code.value
    assert "secret" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("status", "failure_code"),
    [
        (ProviderParityStatus.UNAVAILABLE, EmbeddingTokenizerFailureCode.PROVIDER_PARITY_UNAVAILABLE),
        (ProviderParityStatus.QUARANTINED, EmbeddingTokenizerFailureCode.PROVIDER_PARITY_QUARANTINED),
    ],
)
def test_provider_parity_status_fails_closed_before_downstream_side_effects(
    status: ProviderParityStatus,
    failure_code: EmbeddingTokenizerFailureCode,
) -> None:
    counter = EmbeddingTokenCounter(load_embedding_tokenizer_config())

    with pytest.raises(EmbeddingTokenizerError) as exc_info:
        counter.require_provider_parity(status)

    assert exc_info.value.code is failure_code
    counter.require_provider_parity(ProviderParityStatus.PASSED)


def test_counter_module_has_no_download_character_provider_or_persistence_fallback() -> None:
    module_source = (ROOT / "src" / "rag" / "embedding_tokenizer.py").read_text(encoding="utf-8")

    for forbidden in (
        "huggingface_hub",
        "from_pretrained",
        "requests",
        "httpx",
        "openai",
        "len(text)",
        "PolicyChunk",
        "session.add",
    ):
        assert forbidden not in module_source
