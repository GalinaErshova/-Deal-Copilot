from app.model_gateway import MockProvider
from app.schemas import DealExtraction

def test_mock_gateway_returns_valid_schema():
    provider = MockProvider()
    result = provider.structured(
        model="mock",
        system="test",
        user="test",
        schema=DealExtraction,
    )
    assert isinstance(result, DealExtraction)
    assert result.fields
    assert all(field.key for field in result.fields)
