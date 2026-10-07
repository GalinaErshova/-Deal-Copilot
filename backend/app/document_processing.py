"""Document processing layer adapted from the Ask-Learn ingestion approach.

The important contract is stable: every parser returns ordered blocks with a
source path/page so the UI can compare ORIGINAL vs PARSED and later trace AI
fields back to evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from io import BytesIO
from pathlib import Path
from typing import Any
import json

@dataclass
class ParsedBlock:
    kind: str
    text: str
    path: str
    page_no: int | None = None
    title: str | None = None
    rows: list[list[str]] | None = None

@dataclass
class ParsedDocument:
    parser: str
    confidence: str
    blocks: list[ParsedBlock]
    warnings: list[str]

    def to_json(self) -> str:
        return json.dumps(
            {"parser":self.parser,"confidence":self.confidence,
             "blocks":[asdict(x) for x in self.blocks],"warnings":self.warnings},
            ensure_ascii=False,
        )

    @property
    def plain_text(self) -> str:
        return "\n\n".join(x.text for x in self.blocks if x.text)

def _cell(value: object) -> str:
    return "" if value is None else str(value)

def parse_xlsx(data: bytes) -> ParsedDocument:
    from openpyxl import load_workbook
    book = load_workbook(BytesIO(data), read_only=True, data_only=True)
    blocks: list[ParsedBlock] = []
    for index, sheet in enumerate(book.worksheets, start=1):
        rows = [[_cell(v) for v in row] for row in sheet.iter_rows(values_only=True)]
        rows = [r for r in rows if any(c.strip() for c in r)]
        if not rows:
            continue
        md = "\n".join(" | ".join(r) for r in rows[:5000])
        blocks.append(ParsedBlock("sheet", md, f"/sheet/{index}", title=sheet.title, rows=rows[:5000]))
    return ParsedDocument("xlsx","medium",blocks,[])

def parse_docx(data: bytes) -> ParsedDocument:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    document = Document(BytesIO(data))
    blocks: list[ParsedBlock] = []
    body = document.element.body
    for order, element in enumerate(body.iterchildren(), start=1):
        tag = element.tag.rsplit("}",1)[-1]
        if tag == "tbl":
            table = Table(element, document)
            rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
            text = "\n".join(" | ".join(row) for row in rows)
            blocks.append(ParsedBlock("table",text,f"/table/{order}",rows=rows))
        elif tag == "p":
            p = Paragraph(element, document)
            text = " ".join(p.text.split())
            if text:
                style = (p.style.name if p.style else "").lower()
                blocks.append(ParsedBlock("heading" if style.startswith("heading") else "paragraph",
                                          text,f"/p/{order}",title=text if style.startswith("heading") else None))
    return ParsedDocument("docx","high" if blocks else "low",blocks,[])

def parse_pdf(data: bytes) -> ParsedDocument:
    import fitz
    doc = fitz.open(stream=data, filetype="pdf")
    blocks: list[ParsedBlock] = []
    warnings: list[str] = []
    scanned_pages = 0
    for page_index, page in enumerate(doc, start=1):
        text_blocks = page.get_text("blocks")
        page_text = []
        for idx, block in enumerate(text_blocks, start=1):
            text = " ".join(str(block[4]).split())
            if text:
                page_text.append(text)
                blocks.append(ParsedBlock("paragraph",text,f"/page/{page_index}/p/{idx}",page_no=page_index))
        if not page_text:
            scanned_pages += 1
            blocks.append(ParsedBlock("scan","",f"/page/{page_index}/scan",page_no=page_index))
    if scanned_pages:
        warnings.append(f"{scanned_pages} стр. без текстового слоя: требуется OCR")
    confidence = "high" if blocks and not scanned_pages else "medium" if blocks else "low"
    return ParsedDocument("pdf",confidence,blocks,warnings)

def parse_document(filename: str, content_type: str, data: bytes) -> ParsedDocument:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf" or data.startswith(b"%PDF"):
        return parse_pdf(data)
    if ext == ".docx":
        return parse_docx(data)
    if ext == ".xlsx":
        return parse_xlsx(data)
    raise ValueError(f"Unsupported format: {ext or content_type}")
