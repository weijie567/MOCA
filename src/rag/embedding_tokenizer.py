from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from importlib import metadata
from pathlib import Path
from typing import Final, Literal, NoReturn

from tokenizers import Tokenizer


CONTRACT_VERSION: Final = "embedding_tokenizer.v1"
_ASSET_ROOT: Final = Path(__file__).with_name("assets")
_DEFAULT_CONTRACT_PATH: Final = _ASSET_ROOT / "embedding_tokenizer.v1.json"

_EXPECTED_CONTRACT: Final[dict[str, object]] = {
    "schema_version": CONTRACT_VERSION,
    "provider": "dashscope",
    "model": "text-embedding-v4",
    "dimensions": 1024,
    "tokenizer_source": "Qwen/Qwen3-Embedding-0.6B",
    "tokenizer_revision": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
    "tokenizer_asset_path": "qwen3_embedding_0_6b/tokenizer.json",
    "tokenizer_asset_sha256": "def76fb086971c7867b829c23a26261e38d9d74e02139253b38aeb9df8b4b50a",
    "tokenizer_asset_size_bytes": 11_423_705,
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

_UNSUPPORTED_IDENTITY_FIELDS: Final = frozenset(
    {
        "provider",
        "model",
        "dimensions",
        "tokenizer_source",
        "tokenizer_revision",
        "tokenizer_runtime",
        "normalization",
        "add_special_tokens",
        "assembly_schema_version",
    }
)


class EmbeddingTokenizerFailureCode(str, Enum):
    CONFIG_UNAVAILABLE = "config_unavailable"
    CONFIG_INVALID = "config_invalid"
    UNKNOWN_CONTRACT = "unknown_contract"
    UNSUPPORTED_CONTRACT = "unsupported_contract"
    ASSET_MISSING = "asset_missing"
    ASSET_SIZE_MISMATCH = "asset_size_mismatch"
    ASSET_HASH_MISMATCH = "asset_hash_mismatch"
    RUNTIME_VERSION_MISMATCH = "runtime_version_mismatch"
    TOKENIZER_LOAD_FAILED = "tokenizer_load_failed"
    COUNT_FAILED = "count_failed"
    COUNT_INVALID = "count_invalid"
    COUNT_NONDETERMINISTIC = "count_nondeterministic"
    PROVIDER_PARITY_UNAVAILABLE = "provider_parity_unavailable"
    PROVIDER_PARITY_QUARANTINED = "provider_parity_quarantined"


class ProviderParityStatus(str, Enum):
    PASSED = "passed"
    UNAVAILABLE = "unavailable"
    QUARANTINED = "quarantined"


class EmbeddingTokenizerError(RuntimeError):
    """Safe tokenizer failure containing only an allowlisted reason code."""

    def __init__(self, code: EmbeddingTokenizerFailureCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class EmbeddingTokenizerConfigV1:
    schema_version: Literal["embedding_tokenizer.v1"]
    provider: Literal["dashscope"]
    model: Literal["text-embedding-v4"]
    dimensions: int
    tokenizer_source: str
    tokenizer_revision: str
    tokenizer_asset_path: str
    tokenizer_asset_sha256: str
    tokenizer_asset_size_bytes: int
    tokenizer_runtime: Literal["tokenizers==0.23.1"]
    normalization: Literal["tokenizer_asset_defined"]
    add_special_tokens: Literal[True]
    eos_token: str
    eos_token_id: int
    provider_max_input_tokens: int
    provider_max_batch_inputs: int
    max_embedding_tokens: int
    target_embedding_tokens: int
    overlap_tokens: int
    assembly_schema_version: Literal["policy_embedding_input.v1"]
    mapping_assurance: Literal["empirically_provider_parity_approved_not_vendor_guaranteed"]
    config_fingerprint: str
    _asset_root: Path = field(repr=False, compare=False)

    @property
    def asset_path(self) -> Path:
        return self._asset_root / self.tokenizer_asset_path


def load_embedding_tokenizer_config(contract_path: Path | None = None) -> EmbeddingTokenizerConfigV1:
    selected_path = contract_path or _DEFAULT_CONTRACT_PATH
    try:
        payload = json.loads(selected_path.read_bytes())
    except OSError:
        _fail(EmbeddingTokenizerFailureCode.CONFIG_UNAVAILABLE)
    except (TypeError, ValueError):
        _fail(EmbeddingTokenizerFailureCode.CONFIG_INVALID)

    if not isinstance(payload, dict) or set(payload) != set(_EXPECTED_CONTRACT):
        _fail(EmbeddingTokenizerFailureCode.CONFIG_INVALID)
    if payload.get("schema_version") != CONTRACT_VERSION:
        _fail(EmbeddingTokenizerFailureCode.UNKNOWN_CONTRACT)

    for key, expected in _EXPECTED_CONTRACT.items():
        actual = payload[key]
        if type(actual) is not type(expected):
            _fail(EmbeddingTokenizerFailureCode.CONFIG_INVALID)
        if actual != expected:
            code = (
                EmbeddingTokenizerFailureCode.UNSUPPORTED_CONTRACT
                if key in _UNSUPPORTED_IDENTITY_FIELDS
                else EmbeddingTokenizerFailureCode.CONFIG_INVALID
            )
            _fail(code)

    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fingerprint = "sha256:" + hashlib.sha256(canonical).hexdigest()
    asset_root = selected_path.parent
    return EmbeddingTokenizerConfigV1(
        **payload,
        config_fingerprint=fingerprint,
        _asset_root=asset_root,
    )


class EmbeddingTokenCounter:
    """Deterministic offline counter for the one approved embedding contract."""

    def __init__(self, config: EmbeddingTokenizerConfigV1) -> None:
        self.config = config
        self._verify_runtime()
        asset_bytes = self._read_verified_asset()
        del asset_bytes
        try:
            self._tokenizer = Tokenizer.from_file(str(config.asset_path))
        except Exception:
            _fail(EmbeddingTokenizerFailureCode.TOKENIZER_LOAD_FAILED)

    def count(self, text: str) -> int:
        if not isinstance(text, str):
            _fail(EmbeddingTokenizerFailureCode.COUNT_INVALID)
        try:
            first_ids = tuple(self._tokenizer.encode(text, add_special_tokens=self.config.add_special_tokens).ids)
            second_ids = tuple(self._tokenizer.encode(text, add_special_tokens=self.config.add_special_tokens).ids)
        except Exception:
            _fail(EmbeddingTokenizerFailureCode.COUNT_FAILED)

        if first_ids != second_ids:
            _fail(EmbeddingTokenizerFailureCode.COUNT_NONDETERMINISTIC)
        if not first_ids or any(type(token_id) is not int or token_id < 0 for token_id in first_ids):
            _fail(EmbeddingTokenizerFailureCode.COUNT_INVALID)
        return len(first_ids)

    def require_provider_parity(self, status: ProviderParityStatus) -> None:
        if status is ProviderParityStatus.PASSED:
            return
        if status is ProviderParityStatus.QUARANTINED:
            _fail(EmbeddingTokenizerFailureCode.PROVIDER_PARITY_QUARANTINED)
        _fail(EmbeddingTokenizerFailureCode.PROVIDER_PARITY_UNAVAILABLE)

    def _verify_runtime(self) -> None:
        try:
            actual_version = metadata.version("tokenizers")
        except metadata.PackageNotFoundError:
            _fail(EmbeddingTokenizerFailureCode.RUNTIME_VERSION_MISMATCH)
        if f"tokenizers=={actual_version}" != self.config.tokenizer_runtime:
            _fail(EmbeddingTokenizerFailureCode.RUNTIME_VERSION_MISMATCH)

    def _read_verified_asset(self) -> bytes:
        try:
            asset_bytes = self.config.asset_path.read_bytes()
        except OSError:
            _fail(EmbeddingTokenizerFailureCode.ASSET_MISSING)
        if len(asset_bytes) != self.config.tokenizer_asset_size_bytes:
            _fail(EmbeddingTokenizerFailureCode.ASSET_SIZE_MISMATCH)
        if hashlib.sha256(asset_bytes).hexdigest() != self.config.tokenizer_asset_sha256:
            _fail(EmbeddingTokenizerFailureCode.ASSET_HASH_MISMATCH)
        return asset_bytes


def _fail(code: EmbeddingTokenizerFailureCode) -> NoReturn:
    raise EmbeddingTokenizerError(code) from None
