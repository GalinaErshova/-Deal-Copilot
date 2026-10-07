from app.document_processing import ParsedBlock, ParsedDocument

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
