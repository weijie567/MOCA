from __future__ import annotations

from tests.rag.phase21_xfail_inventory import xfail_for


PARSER_TIMEOUT_SECONDS = 30
OCR_TIMEOUT_SECONDS_PER_PAGE = 15
SAFE_JOB_STATUSES = {"pending", "success", "failed", "review_needed", "rejected"}
FORBIDDEN_REPORT_TERMS = (
    "/Users/ming/private/policy.pdf",
    "Traceback (most recent call last)",
    "raw_bytes",
    "parser_dump",
)


@xfail_for("21-02-03/versioning")
def test_parser_trace_only_metadata_does_not_bump_document_version() -> None:
    from src.rag.versioning import policy_version_fingerprint

    first = policy_version_fingerprint(
        content="七天无理由正文",
        semantic_metadata={"effective_date": "2026-01-01"},
        parser_trace={"parser_version": "pdfplumber-0.11.9", "elapsed_ms": 120},
    )
    second = policy_version_fingerprint(
        content="七天无理由正文",
        semantic_metadata={"effective_date": "2026-01-01"},
        parser_trace={"parser_version": "pdfplumber-0.11.10", "elapsed_ms": 155},
    )

    assert first == second


@xfail_for("21-02-02/transaction-order")
def test_parse_ocr_chunk_and_embed_complete_before_document_write_transaction() -> None:
    from src.rag.ingestion_pipeline import build_ingestion_plan

    plan = build_ingestion_plan(source_path="refund_policy.pdf")

    assert plan.stage_order == [
        "validate",
        "parse",
        "ocr",
        "clean",
        "chunk",
        "embed",
        "begin_write_transaction",
        "replace_document_blocks",
        "replace_policy_chunks",
        "commit",
    ]


@xfail_for("21-02-02/rollback")
def test_failed_parse_ocr_embed_or_db_write_leaves_previous_committed_rows_intact() -> None:
    from src.rag.ingestion_pipeline import simulate_ingestion_failure

    for stage in ("parse", "ocr", "embed", "db_write"):
        result = simulate_ingestion_failure(stage=stage)
        assert result.document_version == "v1"
        assert result.policy_chunks == ["chunk-001"]
        assert result.document_blocks == ["block-001"]
        assert result.source_block_refs_json == [{"source_block_id": "block-001"}]
        assert result.transaction_rolled_back is True


@xfail_for("21-04-02/safe-job-report")
def test_safe_job_report_includes_status_warnings_counts_timings_and_timeout_limits() -> None:
    from src.rag.ingestion_reports import build_safe_ingestion_report

    report = build_safe_ingestion_report(
        {
            "status": "review_needed",
            "warnings": [{"code": "ocr_confidence_review_needed"}],
            "counts": {"pages": 12, "blocks": 42, "chunks": 7},
            "timings": {"parse_ms": 1200, "ocr_ms": OCR_TIMEOUT_SECONDS_PER_PAGE * 1000},
            "limits": {"parser_timeout_seconds": PARSER_TIMEOUT_SECONDS},
        }
    )

    assert report["status"] in SAFE_JOB_STATUSES
    assert report["warnings"][0]["code"] == "ocr_confidence_review_needed"
    assert report["counts"] == {"pages": 12, "blocks": 42, "chunks": 7}
    assert report["timings"]["parse_ms"] == 1200


@xfail_for("21-04-02/raw-payload-report-boundary")
def test_sanitized_failure_reasons_forbid_raw_paths_stack_traces_bytes_and_parser_dumps() -> None:
    from src.rag.ingestion_reports import sanitize_failure_reason

    unsafe_reason = {
        "path": "/Users/ming/private/policy.pdf",
        "stack": "Traceback (most recent call last)",
        "raw_bytes": b"secret-pdf-bytes",
        "parser_dump": {"object": "raw library node"},
    }

    safe_reason = sanitize_failure_reason(unsafe_reason)
    serialized = repr(safe_reason)

    assert safe_reason["failure_code"] == "parser_failed"
    for term in FORBIDDEN_REPORT_TERMS:
        assert term not in serialized

