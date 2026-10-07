from __future__ import annotations

import io
import json
import math
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .document_processing import chunk_extraction_text, parse_document
from .model_gateway import gateway
from .models import (
    Calculation,
    Deal,
    Document,
    ExtractedField,
    PipelineRun,
    PipelineStep,
    ReferenceRate,
    utc_now_naive,
)
from .pricing import calculate
from .schemas import (
    CalculationBreakdownRequest,
    CalculationRequest,
    DealExtraction,
    ManualAreaFieldRequest,
    ProposalExportRequest,
)
from .scope_curator import curate_scope_components
from .scope_extractor import extract_area_components
from .scope_schedule import calculate_monthly_shifts

settings.ensure_dirs()
Base.metadata.create_all(engine)

app = FastAPI(title="Deal Copilot API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.parsed_cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

def seed() -> None:
    db = SessionLocal()
    try:
        if db.query(ReferenceRate).count() == 0:
            for category,name,unit,value,notes in settings.demo_reference_rates:
                db.add(ReferenceRate(category=category,name=name,unit=unit,value=value,notes=notes))
            db.commit()
    finally:
        db.close()
seed()

def _normalize_evidence(text: str | None) -> str:
    return " ".join((text or "").split()).casefold()

def _field_source_is_valid(field, parsed_document: dict) -> bool:
    location = field.source_location or ""
    fragment = _normalize_evidence(field.source_fragment)
    if not location or not fragment:
        return False
    for block in parsed_document.get("blocks", []):
        path = block.get("path", "")
        page = block.get("page_no")
        expected_locations = {path}
        if page:
            expected_locations.add(f"{path} page {page}")
        if location in expected_locations and fragment in _normalize_evidence(block.get("text", "")):
            return True
    return False


def _merge_extractions(extractions: list[DealExtraction]) -> DealExtraction:
    """Объединяет ответы по частям и отмечает разные значения одного поля."""
    fields = []
    missing_fields = []
    contradictions = []
    seen_fields = set()
    seen_missing = set()
    seen_contradictions = set()

    for extraction in extractions:
        for field in extraction.fields:
            identity = (
                field.key,
                field.value,
                field.unit,
                field.source_document,
                field.source_location,
                field.source_fragment,
            )
            if identity not in seen_fields:
                seen_fields.add(identity)
                fields.append(field)
        for missing in extraction.missing_fields:
            if missing not in seen_missing:
                seen_missing.add(missing)
                missing_fields.append(missing)
        for contradiction in extraction.contradictions:
            identity = json.dumps(contradiction, ensure_ascii=False, sort_keys=True)
            if identity not in seen_contradictions:
                seen_contradictions.add(identity)
                contradictions.append(contradiction)

    by_key: dict[str, list] = {}
    for field in fields:
        by_key.setdefault(field.key, []).append(field)
    for key, variants in by_key.items():
        # Группируем по нормализованному значению и единице, чтобы сверить результаты разных частей.
        value_pairs = {
            ((field.value or "").strip().casefold(), (field.unit or "").strip().casefold())
            for field in variants
        }
        if len(value_pairs) > 1:
            contradiction = {
                "key": key,
                "values": [
                    {
                        "value": field.value,
                        "unit": field.unit,
                        "source_document": field.source_document,
                        "source_location": field.source_location,
                        "source_fragment": field.source_fragment,
                    }
                    for field in variants
                ],
            }
            identity = json.dumps(contradiction, ensure_ascii=False, sort_keys=True)
            if identity not in seen_contradictions:
                seen_contradictions.add(identity)
                contradictions.append(contradiction)

    found_keys = set(by_key)
    found_labels = {field.label.casefold() for field in fields}
    missing_fields = [
        item for item in missing_fields
        if item not in found_keys and item.casefold() not in found_labels
    ]
    return DealExtraction(fields=fields, missing_fields=missing_fields, contradictions=contradictions)

@app.get("/api/settings")
def public_settings():
    return {
        "calculation_defaults": settings.calculation_defaults,
        "working_days_per_month": settings.working_days_per_month,
        "working_days_per_week": settings.working_days_per_week,
        "monthly_frequency_shifts": settings.monthly_frequency_shifts,
        "hours_per_shift": settings.hours_per_shift,
        "accepted_upload_extensions": settings.parsed_upload_extensions,
        "demo_mode": settings.is_demo_mode,
        "llm_provider": settings.llm_provider,
        "display_locale": settings.display_locale,
        "currency_code": settings.currency_code,
        "currency_unit_symbol": settings.currency_unit_symbol,
        "display_number_max_fraction_digits": settings.display_number_max_fraction_digits,
        "display_currency_max_fraction_digits": settings.display_currency_max_fraction_digits,
        "display_percentage_factor": settings.display_percentage_factor,
        "display_percentage_decimal_places": settings.display_percentage_decimal_places,
        "base_sensitivity_label": settings.base_sensitivity_label,
        "confidence_good_threshold": settings.confidence_good_threshold,
        "no_bid_margin_threshold": settings.no_bid_margin_threshold,
        "condition_price_decimal_places": settings.condition_price_decimal_places,
        "condition_price_unit": settings.condition_price_unit,
        "sensitivity_bar_min_width": settings.sensitivity_bar_min_width,
        "sensitivity_bar_max_width": settings.sensitivity_bar_max_width,
        "sensitivity_bar_margin_offset": settings.sensitivity_bar_margin_offset,
        "sensitivity_bar_scale": settings.sensitivity_bar_scale,
    }

def add_step(db: Session, run: PipelineRun, name: str, status: str,
             input_data=None, output_data=None, warnings=None, duration_ms=None):
    db.add(PipelineStep(run_id=run.id,name=name,status=status,
                        input_json=json.dumps(input_data,ensure_ascii=False) if input_data is not None else None,
                        output_json=json.dumps(output_data,ensure_ascii=False) if output_data is not None else None,
                        warnings_json=json.dumps(warnings,ensure_ascii=False) if warnings else None,
                        duration_ms=duration_ms))
    db.commit()

@app.get("/api/health")
def health():
    return {"status":"ok","model":settings.llm_default_model,"demo_mode":settings.is_demo_mode}

@app.post("/api/deals")
def create_deal(title: str = "Демо-тендер", db: Session = Depends(get_db)):
    deal = Deal(title=title)
    db.add(deal); db.commit(); db.refresh(deal)
    return {"id":deal.id,"title":deal.title,"status":deal.status}

@app.get("/api/deals")
def list_deals(db: Session = Depends(get_db)):
    deals = db.query(Deal).order_by(Deal.id.desc()).all()
    return [
        {
            "id": deal.id,
            "title": deal.title,
            "status": deal.status,
            "created_at": deal.created_at,
            "document_count": len(deal.documents),
        }
        for deal in deals
    ]

@app.post("/api/deals/{deal_id}/documents")
async def upload_documents(deal_id: int, files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    deal = db.get(Deal, deal_id)
    if not deal: raise HTTPException(404,"Deal not found")
    if len(files) > settings.max_files_per_upload:
        raise HTTPException(413, f"Не более {settings.max_files_per_upload} файлов за загрузку")

    allowed_extensions = set(settings.parsed_upload_extensions)
    pending_files = []
    total_size = 0
    for upload in files:
        original_name = upload.filename or "file"
        extension = Path(original_name).suffix.lower()
        if extension not in allowed_extensions:
            raise HTTPException(415, f"Формат {extension or '(без расширения)'} не поддерживается")
        data = await upload.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, f"Файл {original_name} превышает лимит размера")
        if not data:
            raise HTTPException(400, f"Файл {original_name} пуст")
        total_size += len(data)
        if total_size > settings.max_upload_total_bytes:
            raise HTTPException(413, "Общий размер файлов превышает лимит загрузки")
        pending_files.append((upload, original_name, data))

    run = PipelineRun(deal_id=deal_id); db.add(run); db.commit(); db.refresh(run)
    accepted=[]
    for f, original_name, data in pending_files:
        filename = f"{uuid.uuid4().hex}_{Path(original_name).name}"
        path = settings.resolve_path(settings.upload_dir) / filename
        path.write_bytes(data)
        doc = Document(deal_id=deal_id,filename=original_name,content_type=f.content_type or "",
                       file_path=str(path),parse_status="uploaded")
        db.add(doc); db.commit(); db.refresh(doc)
        accepted.append({"id":doc.id,"filename":doc.filename})
    add_step(db,run,"upload","success",{"files":[x["filename"] for x in accepted]},{"accepted":accepted})
    run.status="success"; run.finished_at=utc_now_naive(); db.commit()
    return {"run_id":run.id,"documents":accepted}

@app.post("/api/deals/{deal_id}/process")
def process_deal(deal_id: int, db: Session = Depends(get_db)):
    deal=db.get(Deal,deal_id)
    if not deal: raise HTTPException(404,"Deal not found")
    docs=db.query(Document).filter(Document.deal_id==deal_id).all()
    if not docs: raise HTTPException(400,"Upload documents first")
    run=PipelineRun(deal_id=deal_id); db.add(run); db.commit(); db.refresh(run)

    combined=[]
    for doc in docs:
        started=time.perf_counter()
        try:
            parsed=parse_document(
                doc.filename,
                doc.content_type,
                settings.resolve_path(doc.file_path).read_bytes(),
                max_spreadsheet_rows=settings.max_spreadsheet_rows,
            )
            doc.parser=parsed.parser; doc.parse_confidence=parsed.confidence
            doc.extracted_text=parsed.plain_text; doc.parse_json=parsed.to_json(); doc.parse_status="parsed"
            db.commit()
            combined.append(parsed.extraction_text(f"{doc.id}:{doc.filename}"))
            add_step(db,run,f"parse:{doc.filename}","success",
                     {"document_id":doc.id},{"parser":parsed.parser,"blocks":len(parsed.blocks),"confidence":parsed.confidence},
                     parsed.warnings,int((time.perf_counter()-started)*1000))
        except Exception as exc:  # noqa: BLE001 — isolate a bad document and continue the batch
            doc.parse_status="failed"; db.commit()
            add_step(db,run,f"parse:{doc.filename}","failed",{"document_id":doc.id},{"error":str(exc)})
    if not combined:
        run.status="failed"; run.finished_at=utc_now_naive(); db.commit()
        raise HTTPException(422,"Не удалось извлечь текст ни из одного документа")
    prompt_text="\n\n".join(combined)[:settings.max_extraction_chars]
    started=time.perf_counter()
    try:
        local_model = settings.llm_provider == "local" and not settings.is_demo_mode
        chunks = chunk_extraction_text(prompt_text, settings.llm_input_chunk_chars) if local_model else [prompt_text]
        partial_extractions = [
            gateway.structured(
                task="extract_requirements",
                system=settings.extraction_system_prompt,
                user=chunk,
                schema=DealExtraction,
            )
            for chunk in chunks
        ]
        extraction = _merge_extractions(partial_extractions) if len(partial_extractions) > 1 else partial_extractions[0]
    except Exception as exc:
        run.status="failed"; run.finished_at=utc_now_naive(); db.commit()
        add_step(db,run,"ai_extraction","failed",{"documents":len(docs)},
                 {"error":str(exc),"prompt_version":settings.extraction_prompt_version})
        raise HTTPException(502,"Не удалось обработать документы моделью") from exc
    db.query(ExtractedField).filter(ExtractedField.deal_id==deal_id).delete()
    document_by_marker={f"{doc.id}:{doc.filename}":doc for doc in docs}
    parsed_by_document_id = {
        doc.id: json.loads(doc.parse_json) if doc.parse_json else {"blocks": []}
        for doc in docs
    }
    for field in extraction.fields:
        source_doc = document_by_marker.get(field.source_document or "")
        source_verified = bool(
            source_doc
            and _field_source_is_valid(
                field,
                parsed_by_document_id.get(source_doc.id, {"blocks": []}),
            )
        )
        db.add(ExtractedField(deal_id=deal_id,key=field.key,label=field.label,value=field.value,
                              unit=field.unit,status="source_verified" if source_verified else "source_unverified",
                              confidence=field.confidence,
                              source_document_id=source_doc.id if source_doc else None,
                              source_location=field.source_location,source_fragment=field.source_fragment))
    db.commit()
    add_step(db,run,"ai_extraction","success",{"documents":len(docs), "chunks":len(chunks)},
             {**extraction.model_dump(),"prompt_version":settings.extraction_prompt_version},
             duration_ms=int((time.perf_counter()-started)*1000))
    run.status="success"; run.finished_at=utc_now_naive(); db.commit()
    return extraction

@app.get("/api/deals/{deal_id}/documents")
def documents(deal_id:int, db: Session=Depends(get_db)):
    docs=db.query(Document).filter(Document.deal_id==deal_id).all()
    return [{"id":d.id,"filename":d.filename,"parser":d.parser,"confidence":d.parse_confidence,
             "status":d.parse_status,"warnings":(json.loads(d.parse_json).get("warnings",[]) if d.parse_json else [])} for d in docs]

@app.get("/api/documents/{document_id}/original")
def document_original(document_id:int, db:Session=Depends(get_db)):
    doc=db.get(Document,document_id)
    if not doc: raise HTTPException(404,"Document not found")
    return FileResponse(settings.resolve_path(doc.file_path),media_type=doc.content_type or "application/octet-stream",filename=doc.filename)

@app.get("/api/documents/{document_id}/parsed")
def document_parsed(document_id:int, db:Session=Depends(get_db)):
    doc=db.get(Document,document_id)
    if not doc: raise HTTPException(404,"Document not found")
    return json.loads(doc.parse_json) if doc.parse_json else {"blocks":[],"warnings":[]}

@app.get("/api/deals/{deal_id}/fields")
def fields(deal_id:int,db:Session=Depends(get_db)):
    rows=db.query(ExtractedField).filter(ExtractedField.deal_id==deal_id).all()
    return [{"id":r.id,"key":r.key,"label":r.label,"value":r.value,"unit":r.unit,"status":r.status,
             "confidence":r.confidence,"source_document_id":r.source_document_id,
             "source_location":r.source_location,"source_fragment":r.source_fragment,"confirmed":r.confirmed} for r in rows]

def _productivity_reference(component:dict, rates:list[ReferenceRate])->ReferenceRate|None:
    normalized_type=str(component.get("work_type") or "").casefold()
    is_snow="снег" in normalized_type or "механизирован" in normalized_type
    for rate in rates:
        name=str(rate.name or "").casefold()
        unit=str(rate.unit or "").casefold().replace(" ", "")
        if unit not in {"м²/смену", "м2/смену"} or rate.value <= 0:
            continue
        rate_is_snow=any(token in name for token in ("снег", "территор", "механизирован"))
        if rate_is_snow == is_snow and (is_snow or "регуляр" in name or "помещ" in name):
            return rate
    return None

@app.get("/api/deals/{deal_id}/area-components")
def area_components(deal_id:int, db:Session=Depends(get_db)):
    if not db.get(Deal, deal_id): raise HTTPException(404,"Deal not found")
    docs=db.query(Document).filter(Document.deal_id==deal_id).order_by(Document.id).all()
    components=extract_area_components(docs)
    components=curate_scope_components(docs,components)
    rates=db.query(ReferenceRate).filter(ReferenceRate.category=="productivity").all()
    for component in components:
        rate=_productivity_reference(component,rates)
        component["productivity_m2_per_shift"]=rate.value if rate else None
        component["productivity_reference"]=(
            {"id":rate.id,"name":rate.name,"unit":rate.unit,"value":rate.value,"notes":rate.notes}
            if rate else None
        )
        component["shifts_per_month"]=calculate_monthly_shifts(
            str(component.get("schedule_mode") or "unspecified"),
            working_days_per_month=settings.working_days_per_month,
            working_days_per_week=settings.working_days_per_week,
            monthly_frequency_shifts=settings.monthly_frequency_shifts,
        )
    return components

@app.patch("/api/fields/{field_id}")
def update_field(field_id:int,payload:dict,db:Session=Depends(get_db)):
    row=db.get(ExtractedField,field_id)
    if not row: raise HTTPException(404,"Field not found")
    if "value" in payload: row.value=str(payload["value"]) if payload["value"] is not None else None
    row.confirmed=bool(payload.get("confirmed",True))
    row.status="user_changed" if "value" in payload else "user_confirmed"
    db.commit()
    return {"ok":True}

@app.post("/api/deals/{deal_id}/fields/area")
def create_manual_area_field(deal_id:int,payload:ManualAreaFieldRequest,db:Session=Depends(get_db)):
    if not db.get(Deal,deal_id): raise HTTPException(404,"Deal not found")
    row=ExtractedField(deal_id=deal_id,key="area_m2",label="Площадь",value=str(payload.value),unit="м²",
                       status="manual_unverified",confirmed=False)
    db.add(row); db.commit(); db.refresh(row)
    return {"id":row.id,"key":row.key,"value":row.value,"confirmed":row.confirmed}

@app.get("/api/deals/{deal_id}/pipeline")
def pipeline(deal_id:int,db:Session=Depends(get_db)):
    runs=db.query(PipelineRun).filter(PipelineRun.deal_id==deal_id).order_by(PipelineRun.id.desc()).all()
    result=[]
    for run in runs:
        steps=db.query(PipelineStep).filter(PipelineStep.run_id==run.id).order_by(PipelineStep.id).all()
        result.append({"id":run.id,"status":run.status,"started_at":run.started_at,"finished_at":run.finished_at,
            "steps":[{"name":s.name,"status":s.status,"duration_ms":s.duration_ms,
                      "input":json.loads(s.input_json) if s.input_json else None,
                      "output":json.loads(s.output_json) if s.output_json else None,
                      "warnings":json.loads(s.warnings_json) if s.warnings_json else []} for s in steps]})
    return result

@app.get("/api/reference-rates")
def reference_rates(db:Session=Depends(get_db)):
    return [{"id":r.id,"category":r.category,"name":r.name,"unit":r.unit,"value":r.value,"notes":r.notes}
            for r in db.query(ReferenceRate).all()]

@app.post("/api/deals/{deal_id}/calculate")
def calculate_deal(deal_id:int,req:CalculationRequest,db:Session=Depends(get_db)):
    if not db.get(Deal,deal_id): raise HTTPException(404,"Deal not found")
    confirmed_area = db.query(ExtractedField).filter(
        ExtractedField.deal_id==deal_id,
        ExtractedField.key=="area_m2",
        ExtractedField.confirmed.is_(True),
    ).first()
    if not confirmed_area or not confirmed_area.value:
        raise HTTPException(409,"Подтвердите площадь объекта перед расчётом")
    try:
        confirmed_area_value = float(confirmed_area.value.replace(",", "."))
    except ValueError:
        raise HTTPException(409,"Подтверждённая площадь указана некорректно")
    if not math.isfinite(confirmed_area_value) or confirmed_area_value <= 0:
        raise HTTPException(409,"Подтверждённая площадь должна быть больше нуля")
    if not math.isclose(req.area_m2, confirmed_area_value, rel_tol=settings.area_match_tolerance):
        raise HTTPException(409,"Площадь расчёта отличается от подтверждённой площади")
    run=PipelineRun(deal_id=deal_id); db.add(run); db.commit(); db.refresh(run)
    started=time.perf_counter()
    result=calculate(req, settings)
    calc=Calculation(deal_id=deal_id,input_json=req.model_dump_json(),
                     output_json=result.model_dump_json(),decision=result.decision)
    db.add(calc)
    deal=db.get(Deal,deal_id); deal.status="calculated"; db.commit(); db.refresh(calc)
    add_step(
        db,run,"deterministic_calculation","success",
        req.model_dump(),
        {"calculation_id":calc.id,**result.model_dump()},
        duration_ms=int((time.perf_counter()-started)*1000),
    )
    run.status="success"; run.finished_at=utc_now_naive(); db.commit()
    return {"calculation_id":calc.id,**result.model_dump()}

@app.post("/api/deals/{deal_id}/calculate-breakdown")
def calculate_deal_breakdown(deal_id:int,req:CalculationBreakdownRequest,db:Session=Depends(get_db)):
    deal=db.get(Deal,deal_id)
    if not deal: raise HTTPException(404,"Deal not found")
    docs=db.query(Document).filter(Document.deal_id==deal_id).order_by(Document.id).all()
    source_components=curate_scope_components(docs,extract_area_components(docs))
    source_by_id={component["id"]:component for component in source_components}
    requested_ids={component.id for component in req.components}
    if not source_by_id:
        raise HTTPException(409,"В документах не найдена таблица площадей с адресами")
    if requested_ids!=set(source_by_id):
        raise HTTPException(409,"Состав адресов и площадей изменился. Обновите страницу и проверьте источники")
    if any(component["curation_status"]!="verified" for component in source_components):
        raise HTTPException(409,"Куратор обнаружил непроверенные источники или неоднозначные строки. Исправьте данные документов перед расчётом")
    if any(component["schedule_status"]=="needs_review" for component in source_components):
        raise HTTPException(409,"Куратор не смог подтвердить источник режима уборки; проверьте цитаты в документе")
    if not req.confirmed:
        raise HTTPException(409,"Подтвердите расчёт целиком после проверки исходных данных и предположений")

    items_by_id={component.id:component for component in req.components}
    shifts_by_id: dict[str, float] = {}
    for source in source_components:
        item=items_by_id[source["id"]]
        if item.productivity_m2_per_shift is None:
            raise HTTPException(409,f"Задайте выработку для строки «{source['address']} — {source['work_type']}»")
        shifts=calculate_monthly_shifts(
            item.schedule_mode,
            working_days_per_month=settings.working_days_per_month,
            working_days_per_week=settings.working_days_per_week,
            monthly_frequency_shifts=settings.monthly_frequency_shifts,
            manual_shifts=item.shifts_per_month,
        )
        if shifts is None or shifts<=0:
            raise HTTPException(409,f"Укажите ожидаемое число смен в месяц для строки «{source['address']} — {source['work_type']}»")
        shifts_by_id[source["id"]]=shifts

    total_area=sum(items_by_id[component["id"]].area_m2 for component in source_components)
    total_workload=sum(
        items_by_id[component["id"]].area_m2
        / items_by_id[component["id"]].productivity_m2_per_shift
        * shifts_by_id[component["id"]]
        for component in source_components
    )
    if total_area<=0 or total_workload<=0:
        raise HTTPException(409,"Для расчёта нужна положительная площадь и производительность")

    line_results=[]
    productivity_rates=db.query(ReferenceRate).filter(ReferenceRate.category=="productivity").all()
    for source in source_components:
        item=items_by_id[source["id"]]
        rate=_productivity_reference(source,productivity_rates)
        shifts=shifts_by_id[source["id"]]
        labor_hours=(item.area_m2/item.productivity_m2_per_shift*settings.hours_per_shift*shifts)
        fte=labor_hours/req.assumptions.monthly_hours_per_fte
        line_results.append({
            **source,
            "area_m2":item.area_m2,
            "productivity_m2_per_shift":item.productivity_m2_per_shift,
            "schedule_mode":item.schedule_mode,
            "shifts_per_month":shifts,
            "productivity_reference":({"id":rate.id,"name":rate.name,"unit":rate.unit,"notes":rate.notes} if rate else None),
            "labor_hours_month":round(labor_hours,settings.labor_hours_decimal_places),
            "fte":round(fte,settings.fte_decimal_places),
            "physical_staff":max(settings.minimum_physical_staff,math.ceil(fte*req.assumptions.replacement_coefficient)),
        })

    effective_productivity=total_area*settings.working_days_per_month/total_workload
    calculation_request=req.assumptions.model_copy(update={
        "area_m2":total_area,
        "productivity_m2_per_shift":effective_productivity,
    })
    aggregate=calculate(calculation_request,settings)
    output={
        "confirmed":req.confirmed,
        "components":line_results,
        "total_area_m2":round(total_area,settings.currency_decimal_places),
        "physical_staff_by_site":sum(item["physical_staff"] for item in line_results),
        "aggregate":aggregate.model_dump(),
    }
    run=PipelineRun(deal_id=deal_id);db.add(run);db.commit();db.refresh(run)
    calc=Calculation(deal_id=deal_id,input_json=req.model_dump_json(),
                     output_json=json.dumps(output,ensure_ascii=False),decision=aggregate.decision)
    db.add(calc);deal.status="calculated";db.commit();db.refresh(calc)
    add_step(db,run,"deterministic_calculation_by_area","success",
             req.model_dump(),{"calculation_id":calc.id,**output})
    run.status="success";run.finished_at=utc_now_naive();db.commit()
    return {"calculation_id":calc.id,**aggregate.model_dump(),**output}

@app.get("/api/deals/{deal_id}/calculations")
def calculations(deal_id:int,db:Session=Depends(get_db)):
    rows=db.query(Calculation).filter(Calculation.deal_id==deal_id).order_by(Calculation.id.desc()).all()
    return [{"id":r.id,"created_at":r.created_at,"decision":r.decision,
             "input":json.loads(r.input_json),"output":json.loads(r.output_json)} for r in rows]

@app.post("/api/deals/{deal_id}/proposal")
def export_proposal(deal_id:int,req:ProposalExportRequest,db:Session=Depends(get_db)):
    """Формирует редактируемый проект КП из подтверждённых требований и последнего расчёта."""
    deal=db.get(Deal,deal_id)
    if not deal:
        raise HTTPException(404,"Deal not found")
    calculation=db.query(Calculation).filter(Calculation.deal_id==deal_id).order_by(Calculation.id.desc()).first()
    if not calculation:
        raise HTTPException(409,"Сначала выполните расчёт экономики сделки")

    from docx import Document as WordDocument
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    output=json.loads(calculation.output_json)
    aggregate=output.get("aggregate",output)
    components=output.get("components",[])
    calculation_input=json.loads(calculation.input_json)
    assumptions=calculation_input.get("assumptions",calculation_input)
    price_per_m2=float(assumptions.get("service_price_per_m2_month",0))
    doc=WordDocument()
    title=doc.add_heading("Коммерческое предложение",0)
    title.alignment=WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Заказчик: {req.customer_name.strip() or '[указать заказчика]'}")
    doc.add_paragraph(f"Исполнитель: {req.supplier_name.strip() or '[указать исполнителя]'}")
    if req.contact_details.strip():
        doc.add_paragraph(f"Контакты: {req.contact_details.strip()}")
    doc.add_paragraph(f"Предложение действительно {req.validity_days} календарных дней с даты подготовки.")
    doc.add_heading("Предмет предложения",level=1)
    doc.add_paragraph("Оказание услуг по уборке объектов на условиях и в объёме, указанных ниже.")

    if components:
        doc.add_heading("Объекты и виды работ",level=1)
        table=doc.add_table(rows=1,cols=6)
        table.style="Light Shading Accent 1"
        for cell,value in zip(table.rows[0].cells,["Адрес","Вид работ","Площадь, м²","Режим","Тариф, ₽/м²·мес.","Стоимость, ₽/мес."]):
            cell.text=value
        for item in components:
            row=table.add_row().cells
            area=float(item.get("area_m2",0) or 0)
            rate=f"{price_per_m2:,.2f}".replace(","," ").replace(".",",")
            monthly=f"{area*price_per_m2:,.2f}".replace(","," ").replace(".",",")
            for cell,value in zip(row,[item.get("address","[уточнить]"),item.get("work_type","[уточнить]"),
                str(item.get("area_m2","—")),item.get("schedule_label",item.get("schedule_mode","[уточнить]")),rate,monthly]):
                cell.text=str(value)

    confirmed_fields=db.query(ExtractedField).filter(
        ExtractedField.deal_id==deal_id,ExtractedField.confirmed.is_(True)
    ).order_by(ExtractedField.id).all()
    confirmed_term=next((field.value for field in confirmed_fields if field.key=="contract_months" and field.value),None)
    try:
        contract_months=int(confirmed_term) if confirmed_term else int(assumptions.get("contract_months",1))
    except (TypeError,ValueError):
        contract_months=int(assumptions.get("contract_months",1))
    if confirmed_fields:
        doc.add_heading("Подтверждённые условия",level=1)
        for field in confirmed_fields:
            if field.key=="area_m2" and components:
                continue
            doc.add_paragraph(f"{field.label}: {field.value or '—'} {field.unit or ''}".strip(),style="List Bullet")

    doc.add_heading("Стоимость услуг",level=1)
    monthly_price=f"{aggregate.get('revenue_with_vat',0):,.2f}".replace(","," ").replace(".",",")
    doc.add_paragraph(f"Стоимость за месяц: {monthly_price} ₽, включая НДС при его применении.")
    doc.add_paragraph(f"Срок оказания услуг: {contract_months} мес.")
    contract_price=f"{aggregate.get('revenue_with_vat',0)*contract_months:,.2f}".replace(","," ").replace(".",",")
    doc.add_paragraph(f"Общая стоимость за срок договора: {contract_price} ₽.")
    doc.add_paragraph("Налоговый режим и ставка НДС подлежат проверке и уточнению перед отправкой.")
    if req.additional_terms.strip():
        doc.add_heading("Дополнительные условия",level=1)
        doc.add_paragraph(req.additional_terms.strip())
    doc.add_paragraph("Проект сформирован по подтверждённым данным сделки. Проверьте реквизиты, налогообложение и договорные условия перед отправкой заказчику.")

    buffer=io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return StreamingResponse(buffer,media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition":f'attachment; filename="commercial-proposal-deal-{deal_id}.docx"'})
