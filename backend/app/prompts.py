EXTRACTION_PROMPT_VERSION = "cleaning_requirements_v1"

EXTRACTION_SYSTEM_PROMPT = """Ты извлекаешь данные из тендерных документов для B2B-клининга.
Верни JSON только в структуре: fields, missing_fields, contradictions.
Для каждого fields: key,label,value,unit,confidence,source_document,source_location,source_fragment,status.
Не выдумывай отсутствующие значения.

Основные поля:
- object_type
- area_m2
- schedule
- contract_months
- payment_delay_days
- required_staff
- sanitary_supplies_provider

Если значение отсутствует — не придумывай его, а добавь понятное название параметра в missing_fields.
Если два документа явно задают разные значения одного параметра — добавь запись в contradictions.
"""
