from __future__ import annotations

import pytest


PHASE21_XFAIL_OWNERS: dict[str, str] = {
    "21-02-03/search-text": "21-02-03",
    "21-02-03/versioning": "21-02-03",
    "21-03-01/runtime-safety": "21-03-01",
    "21-03-02/image-ocr": "21-03-02",
    "21-03-02/ocr-confidence-metadata": "21-03-02",
    "21-03-02/ocr-confidence-gates": "21-03-02",
    "21-03-03/pdf-adapter": "21-03-03",
    "21-03-03/docx-adapter": "21-03-03",
    "21-04-01/provenance-lookup": "21-04-01",
    "21-04-02/safe-job-report": "21-04-02",
    "21-04-02/raw-payload-report-boundary": "21-04-02",
    "21-04a-01/prompt-api-memory-boundary": "21-04a-01",
}


def xfail_for(marker_id: str) -> pytest.MarkDecorator:
    owner_task = PHASE21_XFAIL_OWNERS[marker_id]
    return pytest.mark.xfail(
        strict=True,
        reason=f"phase21 owner_task={owner_task} target code absent",
    )
