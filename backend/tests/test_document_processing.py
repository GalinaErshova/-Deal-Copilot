from io import BytesIO

from openpyxl import Workbook

from app.document_processing import ParsedBlock, ParsedDocument, chunk_extraction_text
from app.main import _field_source_is_valid
from app.schemas import DealExtraction, FieldEvidence


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


def test_chunk_extraction_text_keeps_source_markers_and_respects_limit():
    text = "[DOCUMENT=7:ТЗ.docx PATH=/p/1 KIND=paragraph]\n" + ("Требование по графику. " * 90)

    chunks = chunk_extraction_text(text, max_chars=180)

    assert len(chunks) > 1
    assert all(len(chunk) <= 180 for chunk in chunks)
    assert all(chunk.startswith("[DOCUMENT=7:ТЗ.docx PATH=/p/1 KIND=paragraph]\n") for chunk in chunks)
    assert "Требование по графику." in " ".join(chunks)


def test_merge_extractions_records_conflicting_values_across_chunks():
    from app.main import _merge_extractions

    first = FieldEvidence(
        key="area_m2", label="Площадь", value="1200", unit="м²",
        source_document="1:dogovor.docx", source_location="/p/1", source_fragment="Площадь 1200 м²",
    )
    second = FieldEvidence(
        key="area_m2", label="Площадь", value="1500", unit="м²",
        source_document="2:tehnicheskoe-zadanie.docx", source_location="/p/2", source_fragment="Площадь 1500 м²",
    )

    result = _merge_extractions([
        DealExtraction(fields=[first], missing_fields=["area_m2", "schedule"]),
        DealExtraction(fields=[second], missing_fields=["schedule"]),
    ])

    assert len(result.fields) == 2
    assert result.missing_fields == ["schedule"]
    assert any(item.get("key") == "area_m2" for item in result.contradictions)


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


def test_field_evidence_normalizes_numeric_model_values():
    field = FieldEvidence(key="area_m2", label="Площадь", value=1200, unit="м²")

    assert field.value == "1200"
