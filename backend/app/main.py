from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .document_processing import parse_document
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
from .schemas import CalculationRequest, DealExtraction, ManualAreaFieldRequest

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

@app.get("/api/settings")
def public_settings():
    return {
        "calculation_defaults": settings.calculation_defaults,
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
    return [{"id":d.id,"title":d.title,"status":d.status,"created_at":d.created_at} for d in db.query(Deal).order_by(Deal.id.desc()).all()]

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
        path = Path(settings.upload_dir)/filename
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
                Path(doc.file_path).read_bytes(),
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
        extraction = gateway.structured(
            task="extract_requirements",
            system=settings.extraction_system_prompt,
            user=prompt_text,
            schema=DealExtraction,
        )
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
    add_step(db,run,"ai_extraction","success",{"documents":len(docs)},
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
    return FileResponse(doc.file_path,media_type=doc.content_type or "application/octet-stream",filename=doc.filename)

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

@app.get("/api/deals/{deal_id}/calculations")
def calculations(deal_id:int,db:Session=Depends(get_db)):
    rows=db.query(Calculation).filter(Calculation.deal_id==deal_id).order_by(Calculation.id.desc()).all()
    return [{"id":r.id,"created_at":r.created_at,"decision":r.decision,
             "input":json.loads(r.input_json),"output":json.loads(r.output_json)} for r in rows]
