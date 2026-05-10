from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkResult:
    doc_key: str
    chunk_id: str
    section: str
    content: str
    chunk_index: int
    part_index: int | None = None


_HEADING_PATTERN = re.compile(r"^#{2,3}\s+(.+?)\s*$", re.MULTILINE)
_SENTENCE_BOUNDARIES = "。！？\n"
_FALLBACK_BOUNDARIES = " ，,"


def chunk_markdown(
    content: str,
    doc_key: str,
    max_chars: int = 1200,
    target_chars: int = 800,
    overlap_chars: int = 100,
) -> list[ChunkResult]:
    """Split Markdown policy text into stable heading-based chunks."""
    if not doc_key:
        raise ValueError("doc_key must not be empty")
    if max_chars <= 0 or target_chars <= 0:
        raise ValueError("max_chars and target_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must not be negative")
    if overlap_chars >= target_chars:
        raise ValueError("overlap_chars must be smaller than target_chars")

    chunks: list[ChunkResult] = []
    chunk_index = 0

    for section, body in _iter_sections(content):
        if not body:
            continue

        if len(body) <= max_chars:
            chunks.append(
                ChunkResult(
                    doc_key=doc_key,
                    chunk_id=f"{doc_key}_{chunk_index:03d}",
                    section=section,
                    content=body,
                    chunk_index=chunk_index,
                )
            )
        else:
            for part_index, part in enumerate(_split_oversized(body, max_chars, target_chars, overlap_chars), start=1):
                chunks.append(
                    ChunkResult(
                        doc_key=doc_key,
                        chunk_id=f"{doc_key}_{chunk_index:03d}_part_{part_index}",
                        section=section,
                        content=part,
                        chunk_index=chunk_index,
                        part_index=part_index,
                    )
                )
        chunk_index += 1

    return chunks


def _iter_sections(content: str) -> list[tuple[str, str]]:
    matches = list(_HEADING_PATTERN.finditer(content))
    sections: list[tuple[str, str]] = []

    if not matches:
        body = content.strip()
        return [("intro", body)] if body else []

    intro = content[: matches[0].start()].strip()
    if intro:
        sections.append(("intro", intro))

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        body = content[start:end].strip()
        if body:
            sections.append((match.group(1).strip(), body))

    return sections


def _split_oversized(text: str, max_chars: int, target_chars: int, overlap_chars: int) -> list[str]:
    parts: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        remaining = text_len - start
        if remaining <= max_chars:
            part = text[start:].strip()
            if part:
                parts.append(part)
            break

        preferred_end = min(start + target_chars, text_len)
        end = _find_split_position(text, start, preferred_end)
        if end <= start:
            end = min(start + max_chars, text_len)

        part = text[start:end].strip()
        if part:
            parts.append(part)

        next_start = max(end - overlap_chars, start + 1)
        start = _trim_leading_boundary(text, next_start)

    return parts


def _find_split_position(text: str, start: int, preferred_end: int) -> int:
    lower_bound = start + max(1, preferred_end - start - 200)

    for index in range(preferred_end - 1, lower_bound - 1, -1):
        if text[index] in _SENTENCE_BOUNDARIES:
            return index + 1

    for index in range(preferred_end - 1, start, -1):
        if text[index] in _FALLBACK_BOUNDARIES:
            return index + 1

    return preferred_end


def _trim_leading_boundary(text: str, start: int) -> int:
    while start < len(text) and text[start] in " \n\t，,。！？":
        start += 1
    return start
