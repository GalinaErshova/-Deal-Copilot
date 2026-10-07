from io import BytesIO

from openpyxl import Workbook

from app.document_processing import ParsedBlock, ParsedDocument
from app.main import _field_source_is_valid
from app.schemas import FieldEvidence


def test_extraction_text_contains_traceable_markers():
    parsed = ParsedDocument(
        parser="pdf",
        confidence="high",
        blocks=[
            ParsedBlock(
                kind="paragraph",
                text="Общая площадь объекта 8426,7 кв.м.",
                path="/page/4/p/3",
                page_no=4,
            )
        ],
        warnings=[],
    )
    text = parsed.extraction_text("ТЗ.pdf")
    assert "[DOCUMENT=ТЗ.pdf" in text
    assert "PATH=/page/4/p/3" in text
    assert "page=4" in text
    assert "8426,7" in text


def test_xlsx_parser_obeys_configured_row_limit():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["header"])
    sheet.append(["row 1"])
    sheet.append(["row 2"])
    binary = BytesIO()
    workbook.save(binary)

    from app.document_processing import parse_xlsx

    parsed = parse_xlsx(binary.getvalue(), max_rows=2)
    assert len(parsed.blocks[0].rows) == 2
    assert parsed.warnings


def test_field_source_requires_matching_path_and_verbatim_fragment():
    document = {
        "blocks": [{"path": "/page/4/p/3", "page_no": 4, "text": "Общая площадь 8426,7 кв. м."}]
    }
    verified = FieldEvidence(
        key="area_m2",
        label="Площадь",
        value="8426,7",
        source_location="/page/4/p/3 page 4",
        source_fragment="Общая площадь 8426,7 кв. м.",
    )
    fabricated_quote = verified.model_copy(update={"source_fragment": "Общая площадь 9000 кв. м."})
    wrong_location = verified.model_copy(update={"source_location": "/page/3/p/1 page 3"})

    assert _field_source_is_valid(verified, document)
    assert not _field_source_is_valid(fabricated_quote, document)
    assert not _field_source_is_valid(wrong_location, document)
