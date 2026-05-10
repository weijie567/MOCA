---
phase: 2
plan_id: "01"
title: "Schema Migration + Dependencies + Pydantic Schemas"
wave: 1
depends_on: []
files_modified:
  - src/db/models.py
  - pyproject.toml
  - src/rag/__init__.py
  - src/rag/schemas.py
  - src/db/migrations/versions/002_rag_pipeline.py
autonomous: true
requirements: [RAG-02, RAG-03]
---

# Plan 01: Schema Migration + Dependencies + Pydantic Schemas

<objective>
Fix PolicyChunk embedding column from Vector(1536) to Vector(1024), add `doc_key` semantic ID column to PolicyDocument, add HNSW index, add `openai` dependency, and create Pydantic schemas for the RAG pipeline.
</objective>

<tasks>

<task id="01.1">
<title>Add openai dependency</title>
<read_first>
- pyproject.toml
</read_first>
<action>
Add `"openai>=1.30"` to the `[project.dependencies]` section of pyproject.toml. Run `uv lock` to update the lockfile.
</action>
<acceptance_criteria>
- pyproject.toml contains `"openai>=1.30"` in dependencies
- `uv lock` exits 0
</acceptance_criteria>
</task>

<task id="01.2">
<title>Add doc_key column to PolicyDocument model</title>
<read_first>
- src/db/models.py
</read_first>
<action>
Add to `PolicyDocument` class in src/db/models.py:

1. Add `doc_key` column: `doc_key: Mapped[str] = mapped_column(String(64), nullable=False)`
2. Add unique constraint: `__table_args__ = (UniqueConstraint("tenant_id", "doc_key", name="uq_policy_documents_tenant_doc_key"),)`
3. Add index on `chunk_id` in PolicyChunk: add `index=True` to the existing `chunk_id` mapped_column

Also fix embedding dimension:
- Change `embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))` to `embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))`
</action>
<acceptance_criteria>
- src/db/models.py PolicyDocument class contains `doc_key: Mapped[str] = mapped_column(String(64), nullable=False)`
- src/db/models.py contains `UniqueConstraint("tenant_id", "doc_key"`
- src/db/models.py PolicyChunk contains `Vector(1024)` (not 1536)
- src/db/models.py PolicyChunk chunk_id has `index=True`
</acceptance_criteria>
</task>

<task id="01.3">
<title>Create Alembic migration for schema changes</title>
<read_first>
- src/db/models.py
- src/db/migrations/versions/001_initial_schema.py
</read_first>
<action>
Create `src/db/migrations/versions/002_rag_pipeline.py` following the exact style of 001_initial_schema.py:

```python
"""RAG pipeline schema: doc_key, embedding dimension fix, HNSW index

Revision ID: 002_rag_pipeline
Revises: 001_initial_schema
Create Date: 2026-05-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "002_rag_pipeline"
down_revision: str | None = "001_initial_schema"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Add semantic document key column
    op.add_column("policy_documents", sa.Column("doc_key", sa.String(64), nullable=False, server_default=""))
    op.create_unique_constraint("uq_policy_documents_tenant_doc_key", "policy_documents", ["tenant_id", "doc_key"])

    # Fix embedding dimension: 1536 -> 1024
    op.execute("ALTER TABLE policy_chunks ALTER COLUMN embedding TYPE vector(1024)")

    # Add index on chunk_id for citation lookup
    op.create_index("ix_policy_chunks_chunk_id", "policy_chunks", ["chunk_id"])

    # Create HNSW index for cosine similarity search
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_policy_chunks_embedding_hnsw
        ON policy_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 128)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_policy_chunks_embedding_hnsw")
    op.drop_index("ix_policy_chunks_chunk_id", table_name="policy_chunks")
    op.execute("ALTER TABLE policy_chunks ALTER COLUMN embedding TYPE vector(1536)")
    op.drop_constraint("uq_policy_documents_tenant_doc_key", "policy_documents", type_="unique")
    op.drop_column("policy_documents", "doc_key")
```
</action>
<acceptance_criteria>
- src/db/migrations/versions/002_rag_pipeline.py exists
- File has `revision: str = "002_rag_pipeline"`
- File has `down_revision: str | None = "001_initial_schema"`
- File contains `op.add_column("policy_documents"` with `doc_key`
- File contains `ALTER TABLE policy_chunks ALTER COLUMN embedding TYPE vector(1024)`
- File contains `CREATE INDEX IF NOT EXISTS ix_policy_chunks_embedding_hnsw`
- File contains `hnsw (embedding vector_cosine_ops)` with `m = 16, ef_construction = 128`
- File has both `upgrade()` and `downgrade()` functions
</acceptance_criteria>
</task>

<task id="01.4">
<title>Create RAG Pydantic schemas</title>
<read_first>
- src/api/schemas/common.py (ApiResponse pattern)
- src/api/schemas/ (existing schema patterns)
</read_first>
<action>
Create `src/rag/__init__.py` (empty) and `src/rag/schemas.py`:

```python
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    doc_key: str
    chunk_id: str
    title: str
    section: str
    score: float = Field(ge=0.0, le=1.0)
    text: str


class RetrievalResult(BaseModel):
    query: str
    retrieval_status: str = Field(pattern="^(strong_evidence|partial_evidence|no_evidence)$")
    evidence: list[EvidenceItem]
    best_score: float
    fallback_message: str | None = None


class CitationValidation(BaseModel):
    is_valid: bool
    invalid_citations: list[str] = Field(default_factory=list)
    reason: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)
    doc_type: str | None = None
    risk_level: str | None = None
```

Note: The search endpoint will return `ApiResponse(success=True, data=RetrievalResult(...))` — no custom SearchResponse wrapper needed.
</action>
<acceptance_criteria>
- src/rag/__init__.py exists
- src/rag/schemas.py exists
- src/rag/schemas.py contains `class EvidenceItem(BaseModel)` with `doc_key: str` (not doc_id)
- src/rag/schemas.py contains `class RetrievalResult(BaseModel)`
- src/rag/schemas.py contains `class CitationValidation(BaseModel)`
- src/rag/schemas.py contains `class SearchRequest(BaseModel)`
- src/rag/schemas.py does NOT contain `class SearchResponse` (uses ApiResponse instead)
</acceptance_criteria>
</task>

</tasks>

<verification>
- `uv run python -c "from src.rag.schemas import EvidenceItem, RetrievalResult, CitationValidation, SearchRequest; print('OK')"` exits 0
- `grep -c "Vector(1024)" src/db/models.py` returns 1
- `grep -c "Vector(1536)" src/db/models.py` returns 0
- `grep "doc_key" src/db/models.py` shows the column definition
- Migration file exists at correct path with correct down_revision
</verification>

<must_haves>
- Vector dimension is 1024 (not 1536)
- PolicyDocument has doc_key column with tenant-scoped unique constraint
- PolicyChunk.chunk_id has index for citation lookup
- HNSW index with vector_cosine_ops
- openai>=1.30 in dependencies
- Pydantic schemas use doc_key (not doc_id) for semantic identifier
- No custom SearchResponse — endpoint uses ApiResponse
</must_haves>
