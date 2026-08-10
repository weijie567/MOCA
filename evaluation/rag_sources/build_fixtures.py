"""Build the first RAG format-parity fixture set.

The three Markdown files are the source of truth.  This script renders each
source into a selectable-text PDF and a raster-only PDF so parser and retrieval
parity runs can use the same policy content without editing the demo corpus.

Run from the repository root:

    UV_CACHE_DIR=/tmp/uv-cache uv run python evaluation/rag_sources/build_fixtures.py
"""

from __future__ import annotations

import argparse
import hashlib
import html
from importlib.metadata import version
import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pdfplumber
import pypdfium2
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "evaluation" / "rag_sources" / "fixtures"
MANIFEST_PATH = ROOT / "evaluation" / "rag_sources" / "format_parity_manifest.jsonl"
GENERATOR_SCHEMA_VERSION = "rag_format_parity_fixture_generator.v1"
GENERATOR_PROFILE = "moca-format-parity-a4-v1"
DETERMINISTIC_METADATA_PROFILE = "moca-pdf-invariant-v1"
RASTER_DPI = 200
_FIXED_PDF_TIME = time.gmtime(946684800)


class FixtureBuildError(RuntimeError):
    """Stable generator failure that never exposes fixture contents."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class FixtureBuildResult:
    manifest_path: Path
    manifest_hash: str
    fixture_paths: tuple[Path, ...]
    generator_identity: dict[str, object]


@dataclass(frozen=True)
class Topic:
    directory: str
    doc_key: str
    title: str


TOPICS = (
    Topic(
        directory="refund_eligibility_and_return",
        doc_key="eval_refund_eligibility_and_return",
        title="国内普通实物订单退款与退货政策",
    ),
    Topic(
        directory="quality_compensation_and_approval",
        doc_key="eval_quality_compensation_and_approval",
        title="质量问题与补偿审批政策",
    ),
    Topic(
        directory="cross_border_and_digital_goods",
        doc_key="eval_cross_border_and_digital_goods",
        title="跨境订单与数字商品退款例外政策",
    ),
)


def _font_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        if explicit.is_file():
            return explicit
        raise FixtureBuildError("cjk_font_invalid")
    configured = os.environ.get("MOCA_CJK_FONT")
    candidates = [
        Path(configured) if configured else None,
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise RuntimeError(
        "No CJK font found. Set MOCA_CJK_FONT to a Unicode-capable .ttf/.ttc font before generating the PDF fixtures."
    )


def _inline_markup(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<font name='MOCA-CJK-Mono'>\1</font>", escaped)
    return escaped.replace("  ", "<br/>")


def _is_table_row(line: str) -> bool:
    return line.strip().startswith("|") and line.strip().endswith("|")


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _flush_paragraph(story: list[tuple[str, object]], buffer: list[str]) -> None:
    if buffer:
        paragraph = "<br/>".join(_inline_markup(part.strip()) for part in buffer if part.strip())
        if paragraph:
            story.append(("paragraph", paragraph))
        buffer.clear()


def _parse_markdown(text: str) -> list[tuple[str, object]]:
    """Parse the small Markdown subset used by the policy fixtures."""

    lines = text.splitlines()
    story: list[tuple[str, object]] = []
    paragraph: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            _flush_paragraph(story, paragraph)
            index += 1
            continue

        heading = re.match(r"^(#{1,3})\s+(.+?)\s*$", stripped)
        if heading:
            _flush_paragraph(story, paragraph)
            story.append((f"h{len(heading.group(1))}", heading.group(2)))
            index += 1
            continue

        if stripped.startswith(">"):
            paragraph.append(stripped.removeprefix("> ").removeprefix(">"))
            index += 1
            continue

        if stripped.startswith("-") or re.match(r"^\d+[.)]\s+", stripped):
            _flush_paragraph(story, paragraph)
            item = re.sub(r"^(?:-|\d+[.)])\s+", "", stripped)
            story.append(("bullet", item))
            index += 1
            continue

        if _is_table_row(stripped) and index + 1 < len(lines) and "---" in lines[index + 1]:
            _flush_paragraph(story, paragraph)
            rows: list[list[str]] = [_table_cells(stripped)]
            index += 2
            while index < len(lines) and _is_table_row(lines[index]):
                rows.append(_table_cells(lines[index]))
                index += 1
            story.append(("table", rows))
            continue

        paragraph.append(line)
        index += 1

    _flush_paragraph(story, paragraph)
    return story


def _register_fonts(font_path: Path) -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pdfmetrics.registerFont(TTFont("MOCA-CJK", str(font_path)))
    pdfmetrics.registerFont(TTFont("MOCA-CJK-Mono", str(font_path)))


def _styles():
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm

    common = {
        "fontName": "MOCA-CJK",
        "wordWrap": "CJK",
    }
    return {
        "h1": ParagraphStyle(
            "MOCA-H1",
            parent=None,
            fontSize=18,
            leading=25,
            alignment=TA_CENTER,
            spaceAfter=10 * mm,
            textColor="#243447",
            **common,
        ),
        "h2": ParagraphStyle(
            "MOCA-H2",
            parent=None,
            fontSize=13.5,
            leading=19,
            spaceBefore=5 * mm,
            spaceAfter=2.5 * mm,
            textColor="#243447",
            **common,
        ),
        "h3": ParagraphStyle(
            "MOCA-H3",
            parent=None,
            fontSize=11.5,
            leading=16,
            spaceBefore=3.5 * mm,
            spaceAfter=1.5 * mm,
            textColor="#243447",
            **common,
        ),
        "paragraph": ParagraphStyle(
            "MOCA-Body",
            parent=None,
            fontSize=11,
            leading=19,
            alignment=TA_LEFT,
            spaceAfter=3 * mm,
            textColor="#243447",
            **common,
        ),
        "bullet": ParagraphStyle(
            "MOCA-Bullet",
            parent=None,
            fontSize=10.5,
            leading=18,
            leftIndent=5 * mm,
            firstLineIndent=-3 * mm,
            spaceAfter=1.8 * mm,
            textColor="#243447",
            **common,
        ),
        "quote": ParagraphStyle(
            "MOCA-Quote",
            parent=None,
            fontSize=8.8,
            leading=13,
            leftIndent=4 * mm,
            textColor="#536878",
            borderColor="#b6c4d0",
            borderWidth=0.5,
            borderPadding=3 * mm,
            spaceAfter=3 * mm,
            **common,
        ),
        "table": ParagraphStyle(
            "MOCA-Table", parent=None, fontSize=7.8, leading=11, alignment=TA_LEFT, textColor="#243447", **common
        ),
        "table-header": ParagraphStyle(
            "MOCA-TableHeader", parent=None, fontSize=7.8, leading=11, alignment=TA_LEFT, textColor="#243447", **common
        ),
    }


def _table_story(rows: list[list[str]], styles: dict[str, object], page_width: float):
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    width_count = max(len(row) for row in rows)
    normalized = [row + [""] * (width_count - len(row)) for row in rows]
    cells = []
    for row_index, row in enumerate(normalized):
        style_name = "table-header" if row_index == 0 else "table"
        cells.append([Paragraph(_inline_markup(cell), styles[style_name]) for cell in row])

    if width_count == 2:
        widths = [page_width * 0.27, page_width * 0.73]
    elif width_count == 3:
        widths = [page_width * 0.22, page_width * 0.38, page_width * 0.40]
    elif width_count == 4:
        widths = [page_width * 0.18, page_width * 0.27, page_width * 0.26, page_width * 0.29]
    else:
        widths = [page_width / width_count] * width_count

    table = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dceaf1")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9aa9b3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f7f9")]),
            ]
        )
    )
    return table


def _render_digital_pdf(source: Path, output: Path, title: str, *, font_path: Path) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    from reportlab.pdfgen.canvas import Canvas

    _register_fonts(font_path)
    styles = _styles()
    page_width, _ = A4
    usable_width = page_width - 35 * mm
    story = []
    for kind, value in _parse_markdown(source.read_text(encoding="utf-8")):
        if kind in {"h1", "h2", "h3"}:
            story.append(Paragraph(_inline_markup(str(value)), styles[kind]))
        elif kind == "paragraph":
            text = str(value)
            style = (
                styles["quote"] if text.startswith("评测母版") or text.startswith("政策版本") else styles["paragraph"]
            )
            story.append(Paragraph(text, style))
        elif kind == "bullet":
            story.append(Paragraph(f"• {_inline_markup(str(value))}", styles["bullet"]))
        elif kind == "table":
            story.append(_table_story(value, styles, usable_width))
            story.append(Spacer(1, 4 * mm))

    output.parent.mkdir(parents=True, exist_ok=True)

    def decorate_page(canvas, doc):
        canvas.saveState()
        canvas.setAuthor("MOCA evaluation fixtures")
        canvas.setCreator(GENERATOR_SCHEMA_VERSION)
        canvas.setSubject(DETERMINISTIC_METADATA_PROFILE)
        canvas.setTitle(title)
        canvas.setFillColor(HexColor("#536878"))
        canvas.setFont("MOCA-CJK", 7.5)
        canvas.drawString(doc.leftMargin, A4[1] - 13 * mm, f"MOCA RAG 评测 fixture | {title}")
        canvas.drawRightString(A4[0] - doc.rightMargin, 11 * mm, f"第 {doc.page} 页")
        canvas.restoreState()

    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=17.5 * mm,
        rightMargin=17.5 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="MOCA evaluation fixtures",
        invariant=1,
        pageCompression=1,
    )
    document.build(
        story,
        onFirstPage=decorate_page,
        onLaterPages=decorate_page,
        canvasmaker=Canvas,
    )


def _render_scanned_pdf(digital_pdf: Path, output: Path, *, title: str) -> None:
    """Rasterize the digital PDF into a grayscale, text-layer-free PDF."""

    from reportlab.lib.pagesizes import A4

    document = pypdfium2.PdfDocument(str(digital_pdf))
    images: list[Image.Image] = []
    try:
        for page_index in range(len(document)):
            page = document[page_index]
            bitmap = page.render(scale=RASTER_DPI / 72)
            rgb_image = bitmap.to_pil().convert("RGB")
            rgb_image.info.clear()
            images.append(rgb_image)
            close_page = getattr(page, "close", None)
            if callable(close_page):
                close_page()
    finally:
        close_document = getattr(document, "close", None)
        if callable(close_document):
            close_document()

    if not images:
        raise RuntimeError(f"No pages rendered from {digital_pdf}")
    output.parent.mkdir(parents=True, exist_ok=True)
    first, *rest = images
    pdf_resolution = (first.width * 72 / A4[0], first.height * 72 / A4[1])
    first.save(
        output,
        "PDF",
        dpi=pdf_resolution,
        save_all=True,
        append_images=rest,
        title=title,
        author="MOCA evaluation fixtures",
        subject=DETERMINISTIC_METADATA_PROFILE,
        creator=GENERATOR_SCHEMA_VERSION,
        producer=f"Pillow {version('Pillow')}",
        creationDate=_FIXED_PDF_TIME,
        modDate=_FIXED_PDF_TIME,
        quality=95,
        subsampling=0,
        optimize=False,
        progressive=False,
    )


def _pdf_pages(path: Path) -> int:
    document = pypdfium2.PdfDocument(str(path))
    try:
        return len(document)
    finally:
        close_document = getattr(document, "close", None)
        if callable(close_document):
            close_document()


def _digital_text_chars(path: Path) -> int:
    with pdfplumber.open(path) as document:
        return sum(len(page.extract_text() or "") for page in document.pages)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _build_topic(
    topic: Topic,
    *,
    source_fixture_root: Path,
    output_fixture_root: Path,
    output_root: Path,
    font_path: Path,
    generator_identity: dict[str, object],
    generator_identity_hash: str,
) -> tuple[dict[str, object], tuple[Path, ...]]:
    source_directory = source_fixture_root / topic.directory
    output_directory = output_fixture_root / topic.directory
    source_markdown = source_directory / f"{topic.directory}.md"
    markdown = output_directory / f"{topic.directory}.md"
    digital = output_directory / f"{topic.directory}.digital.pdf"
    scanned = output_directory / f"{topic.directory}.scanned.pdf"
    if not source_markdown.is_file():
        raise FixtureBuildError("canonical_markdown_missing")

    output_directory.mkdir(parents=True, exist_ok=True)
    if source_markdown.resolve() != markdown.resolve():
        shutil.copyfile(source_markdown, markdown)

    _render_digital_pdf(markdown, digital, topic.title, font_path=font_path)
    _render_scanned_pdf(digital, scanned, title=topic.title)
    digital_chars = _digital_text_chars(digital)
    scanned_chars = _digital_text_chars(scanned)
    if digital_chars < 1000:
        raise FixtureBuildError("digital_text_layer_invalid")
    if scanned_chars != 0:
        raise FixtureBuildError("scanned_text_layer_invalid")
    if _pdf_pages(digital) != 5 or _pdf_pages(scanned) != 5:
        raise FixtureBuildError("pdf_page_count_invalid")

    variants = []
    for fmt, path, source_type in (
        ("markdown", markdown, "policy_markdown"),
        ("digital_pdf", digital, "policy_pdf"),
        ("scanned_pdf", scanned, "policy_pdf"),
    ):
        variants.append(
            {
                "format": fmt,
                "path": path.relative_to(output_root).as_posix(),
                "source_type": source_type,
                "sha256": _sha256(path),
                "pages": _pdf_pages(path) if path.suffix == ".pdf" else None,
                "extractable_text_chars": digital_chars
                if fmt == "digital_pdf"
                else scanned_chars
                if fmt == "scanned_pdf"
                else len(markdown.read_text(encoding="utf-8")),
            }
        )
    return {
        "parity_group": topic.doc_key,
        "doc_key": topic.doc_key,
        "title": topic.title,
        "source_of_truth": markdown.relative_to(output_root).as_posix(),
        "variants": variants,
        "generator_identity": generator_identity,
        "generator_identity_hash": generator_identity_hash,
    }, (markdown, digital, scanned)


def _generator_identity(*, font_path: Path, profile: str) -> dict[str, object]:
    return {
        "schema_version": GENERATOR_SCHEMA_VERSION,
        "builder_sha256": _sha256(Path(__file__).resolve()),
        "profile": profile,
        "reportlab_version": version("reportlab"),
        "pillow_version": version("Pillow"),
        "pypdfium2_version": version("pypdfium2"),
        "pdfplumber_version": version("pdfplumber"),
        "cjk_font_sha256": _sha256(font_path),
        "raster_dpi": RASTER_DPI,
        "deterministic_metadata_profile": DETERMINISTIC_METADATA_PROFILE,
    }


def _identity_hash(identity: Mapping[str, object]) -> str:
    payload = json.dumps(dict(identity), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def build_fixture_family(
    *,
    repository_root: Path,
    output_root: Path,
    font_path: Path | None = None,
    generator_profile: str = GENERATOR_PROFILE,
    expected_generator_identity: Mapping[str, object] | None = None,
) -> FixtureBuildResult:
    """Build the complete family under explicit source and output roots."""

    source_root = repository_root.resolve()
    destination_root = output_root.resolve()
    source_fixture_root = source_root / "evaluation/rag_sources/fixtures"
    output_fixture_root = destination_root / "evaluation/rag_sources/fixtures"
    manifest_path = destination_root / "evaluation/rag_sources/format_parity_manifest.jsonl"
    if not source_fixture_root.is_dir() or not generator_profile:
        raise FixtureBuildError("generator_input_invalid")

    resolved_font = _font_path(font_path).resolve()
    identity = _generator_identity(font_path=resolved_font, profile=generator_profile)
    if expected_generator_identity is not None and dict(expected_generator_identity) != identity:
        raise FixtureBuildError("generator_identity_mismatch")
    identity_hash = _identity_hash(identity)

    records: list[dict[str, object]] = []
    fixture_paths: list[Path] = []
    for topic in TOPICS:
        record, topic_paths = _build_topic(
            topic,
            source_fixture_root=source_fixture_root,
            output_fixture_root=output_fixture_root,
            output_root=destination_root,
            font_path=resolved_font,
            generator_identity=identity,
            generator_identity_hash=identity_hash,
        )
        records.append(record)
        fixture_paths.extend(topic_paths)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    return FixtureBuildResult(
        manifest_path=manifest_path,
        manifest_hash=_sha256(manifest_path),
        fixture_paths=tuple(fixture_paths),
        generator_identity=identity,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build MOCA RAG format-parity fixtures")
    parser.add_argument("--output-root", type=Path, default=ROOT)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = build_fixture_family(
        repository_root=ROOT,
        output_root=args.output_root,
    )
    print(f"Built {len(TOPICS)} parity groups and {len(result.fixture_paths)} fixtures")
    print(f"Generator identity: {_identity_hash(result.generator_identity)}")
    print(f"Manifest: {result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
