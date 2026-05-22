"""Validate Phase 6 golden-set references against deterministic demo seed IDs.

Deterministic seed facts:
- Users: cs_zhang (support), mgr_li (manager), admin_wang equivalent is demo_admin/admin_user.
- Password: moca2024 for all demo accounts.
- Orders: extracted from seed_demo.py scenario_orders plus generated ORD-2024-007..ORD-2024-086.
- Refund cases: extracted from seed_demo.py scenarios plus generated RF-2024-007..RF-2024-030.
- Tickets: extracted from seed_demo.py key_cases plus generated TK-2024-007..TK-2024-015.
- Agent policy evidence docs: extracted from seed_demo.py seed_policy_documents doc_key tuples.
- RAG policy docs/chunks: generated from data/policies/*.md with src.rag.chunker.chunk_markdown.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEED_PATH = ROOT / "scripts" / "seed_demo.py"
AGENT_GOLDEN_PATH = ROOT / "evaluation" / "golden" / "agent_cases.jsonl"
RAG_GOLDEN_PATH = ROOT / "evaluation" / "golden" / "rag_cases.jsonl"
POLICY_DIR = ROOT / "data" / "policies"

ID_PATTERN = re.compile(r"(?<![A-Za-z0-9_-])(ORD-[A-Z0-9-]+|RFC?-[A-Z0-9-]+|TKT?-[A-Z0-9-]+)(?![A-Za-z0-9_-])")
ORDER_RANGE_PATTERN = re.compile(r"range\((\d+),\s*(\d+)\).*?order_no = f\"ORD-2024-\{index:03d\}\"", re.DOTALL)
REFUND_RANGE_PATTERN = re.compile(
    r"enumerate\(order_numbers, start=(\d+)\).*?case_no = f\"RF-2024-\{index:03d\}\"", re.DOTALL
)
TICKET_RANGE_PATTERN = re.compile(
    r"enumerate\(refund_items, start=(\d+)\).*?ticket_no = f\"TK-2024-\{index:03d\}\"", re.DOTALL
)
DOC_TUPLE_PATTERN = re.compile(r'\("([a-z0-9_]+)",\s*"[^"]+",\s*"[^"]+",\s*"[^"]+"\)')
USER_SPEC_PATTERN = re.compile(
    r'\("(?P<key>demo_[^"]+)",\s*"demo",\s*"(?P<username>[^"]+)",\s*"[^"]+",\s*"(?P<role>[^"]+)"',
)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _extract_rag_corpus_ids(policy_dir: Path) -> dict[str, set[str]]:
    from src.rag.chunker import chunk_markdown

    doc_keys: set[str] = set()
    chunk_ids: set[str] = set()
    for path in sorted(policy_dir.glob("*.md")):
        doc_key = path.stem
        doc_keys.add(doc_key)
        content = path.read_text(encoding="utf-8")
        chunk_ids.update(chunk.chunk_id for chunk in chunk_markdown(content, doc_key=doc_key))
    return {"doc_keys": doc_keys, "chunk_ids": chunk_ids}


def _extract_seed_ids(seed_text: str) -> dict[str, set[str]]:
    orders = {match.group(0) for match in re.finditer(r"\bORD-[0-9]{4}-[0-9]{3}\b", seed_text)}
    refunds = {match.group(0) for match in re.finditer(r"\bRF-[0-9]{4}-[0-9]{3}\b", seed_text)}
    tickets = {match.group(0) for match in re.finditer(r"\bTK-[0-9]{4}-[0-9]{3}\b", seed_text)}

    order_range = ORDER_RANGE_PATTERN.search(seed_text)
    if order_range:
        start, stop = (int(order_range.group(1)), int(order_range.group(2)))
        orders.update(f"ORD-2024-{index:03d}" for index in range(start, stop))

    refund_range = REFUND_RANGE_PATTERN.search(seed_text)
    if refund_range:
        start = int(refund_range.group(1))
        refunds.update(f"RF-2024-{index:03d}" for index in range(start, 31))

    ticket_range = TICKET_RANGE_PATTERN.search(seed_text)
    if ticket_range:
        start = int(ticket_range.group(1))
        tickets.update(f"TK-2024-{index:03d}" for index in range(start, 16))

    doc_keys = set(DOC_TUPLE_PATTERN.findall(seed_text))
    users = {
        match.group("username")
        for match in USER_SPEC_PATTERN.finditer(seed_text)
        if match.group("role") in {"support", "manager", "admin"}
    }
    return {
        "orders": orders,
        "refunds": refunds,
        "tickets": tickets,
        "doc_keys": doc_keys,
        "users": users,
    }


def _expected_bucket(reference: str) -> str:
    if reference.startswith("ORD-"):
        return "orders"
    if reference.startswith(("RF-", "RFC-")):
        return "refunds"
    if reference.startswith(("TK-", "TKT-")):
        return "tickets"
    raise ValueError(f"Unsupported reference type: {reference}")


def _error(case_id: str, issue: str, fix: str) -> str:
    return f"{case_id}: {issue}. Fix: {fix}"


def _validate_rag_cases(rag_corpus_ids: dict[str, set[str]]) -> list[str]:
    errors: list[str] = []
    for expected_index, case in enumerate(_read_jsonl(RAG_GOLDEN_PATH), start=1):
        case_id = f"RAG-{expected_index:02d}"
        should_fallback = bool(case.get("should_fallback"))
        expected_doc_ids = case.get("expected_doc_ids", [])
        expected_chunk_ids = case.get("expected_chunk_ids", [])

        if should_fallback:
            if expected_doc_ids or expected_chunk_ids:
                errors.append(
                    _error(
                        case_id,
                        "fallback case should not declare expected_doc_ids or expected_chunk_ids",
                        "clear expected_doc_ids and expected_chunk_ids for fallback RAG cases",
                    )
                )
            continue

        if not expected_doc_ids:
            errors.append(
                _error(
                    case_id,
                    "non-fallback RAG case has no expected_doc_ids",
                    "add at least one doc_key from data/policies",
                )
            )
        if not expected_chunk_ids:
            errors.append(
                _error(
                    case_id,
                    "non-fallback RAG case has no expected_chunk_ids",
                    "add at least one chunk_id produced by chunk_markdown",
                )
            )

        for doc_key in expected_doc_ids:
            if doc_key not in rag_corpus_ids["doc_keys"]:
                errors.append(
                    _error(
                        case_id,
                        f"references {doc_key} in expected_doc_ids but doc is not in data/policies",
                        "use a data/policies markdown filename stem or add the missing policy document",
                    )
                )

        for chunk_id in expected_chunk_ids:
            if chunk_id not in rag_corpus_ids["chunk_ids"]:
                errors.append(
                    _error(
                        case_id,
                        f"references {chunk_id} in expected_chunk_ids but chunk is not produced by chunk_markdown",
                        "update the chunk_id to match the current data/policies corpus and chunker output",
                    )
                )

    return errors


def validate() -> list[str]:
    seed_ids = _extract_seed_ids(SEED_PATH.read_text(encoding="utf-8"))
    rag_corpus_ids = _extract_rag_corpus_ids(POLICY_DIR)
    errors: list[str] = []
    cases = _read_jsonl(AGENT_GOLDEN_PATH)

    expected_demo_users = {"cs_zhang", "mgr_li", "admin_user"}
    missing_users = expected_demo_users - seed_ids["users"]
    if missing_users:
        errors.append(
            _error(
                "seed_demo.py",
                f"missing expected demo users {sorted(missing_users)}",
                "restore deterministic support, manager, and admin demo users in seed_demo.py",
            )
        )

    seen_ids: set[str] = set()
    for expected_index, case in enumerate(cases, start=1):
        case_id = case.get("id", f"<line {expected_index}>")
        expected_id = f"GS-{expected_index:02d}"
        if case_id in seen_ids:
            errors.append(
                _error(
                    case_id,
                    "case ID is duplicated",
                    "renumber golden set IDs so each case has one unique GS-XX ID",
                )
            )
        seen_ids.add(case_id)
        if case_id != expected_id:
            errors.append(
                _error(
                    case_id,
                    f"case ID is not sequential; expected {expected_id}",
                    "renumber cases from GS-01 through the final line without gaps",
                )
            )

        is_not_found = case.get("category") == "tool_failure_or_not_found"
        for reference in sorted(set(ID_PATTERN.findall(case.get("query", "")))):
            bucket = _expected_bucket(reference)
            if not is_not_found and reference not in seed_ids[bucket]:
                errors.append(
                    _error(
                        case_id,
                        f"references {reference} but category is {case.get('category')} "
                        "(not tool_failure_or_not_found)",
                        "update the reference to an ID generated by scripts/seed_demo.py, "
                        "or use tool_failure_or_not_found for deliberate missing IDs",
                    )
                )

        for doc_key in case.get("expected_evidence_doc_keys", []):
            if doc_key not in seed_ids["doc_keys"]:
                errors.append(
                    _error(
                        case_id,
                        f"references {doc_key} in expected_evidence_doc_keys but doc not in seed policy documents",
                        "use a doc_key from seed_policy_documents() or add the missing policy document to seed_demo.py",
                    )
                )

    errors.extend(_validate_rag_cases(rag_corpus_ids))
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("SEED VALIDATION FAILED:")
        for error in errors:
            print(f"- {error}")
        print("\nFix: Update golden set IDs to match scripts/seed_demo.py output, or run: make seed")
        return 1

    print("SEED VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
