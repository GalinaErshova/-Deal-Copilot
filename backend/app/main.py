from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json, time, uuid

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, get_db, SessionLocal
from .models import Deal, Document, ExtractedField, PipelineRun, PipelineStep, ReferenceRate, Calculation
from .schemas import DealExtraction, CalculationRequest
from .document_processing import parse_document
from .model_gateway import gateway
from .pricing import calculate
from .demo_data import DEMO_REFERENCE_RATES

settings.ensure_dirs()
Base.metadata.create_all(engine)

app = FastAPI(title="Deal Copilot API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

def seed() -> None:
    db = SessionLocal()
    try:
        if db.query(ReferenceRate).count() == 0:
            for category,name,unit,value,notes in DEMO_REFERENCE_RATES:
                db.add(ReferenceRate(category=category,name=name,unit=unit,value=value,notes=notes))
            db.commit()
    finally:
        db.close()
seed()

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
    return {"status":"ok","model":settings.llm_default_model,"demo_mode":settings.demo_mode}

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
    run = PipelineRun(deal_id=deal_id); db.add(run); db.commit(); db.refresh(run)
    accepted=[]
    for f in files:
        data = await f.read()
        filename = f"{uuid.uuid4().hex}_{Path(f.filename or 'file').name}"
        path = Path(settings.upload_dir)/filename
        path.write_bytes(data)
        doc = Document(deal_id=deal_id,filename=f.filename or filename,content_type=f.content_type or "",
                       file_path=str(path),parse_status="uploaded")
        db.add(doc); db.commit(); db.refresh(doc)
        accepted.append({"id":doc.id,"filename":doc.filename})
    add_step(db,run,"upload","success",{"files":[x["filename"] for x in accepted]},{"accepted":accepted})
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
            parsed=parse_document(doc.filename,doc.content_type,Path(doc.file_path).read_bytes())
            doc.parser=parsed.parser; doc.parse_confidence=parsed.confidence
            doc.extracted_text=parsed.plain_text; doc.parse_json=parsed.to_json(); doc.parse_status="parsed"
            db.commit()
            combined.append(f"### {doc.filename}\n{parsed.plain_text}")
            add_step(db,run,f"parse:{doc.filename}","success",
                     {"document_id":doc.id},{"parser":parsed.parser,"blocks":len(parsed.blocks),"confidence":parsed.confidence},
                     parsed.warnings,int((time.perf_counter()-started)*1000))
        except Exception as exc:
            doc.parse_status="failed"; db.commit()
            add_step(db,run,f"parse:{doc.filename}","failed",{"document_id":doc.id},{"error":str(exc)})
    prompt_text="\n\n".join(combined)[:500000]
    started=time.perf_counter()
    system="""Ты извлекаешь данные из тендерных документов для B2B-клининга.
Верни JSON только в структуре: fields, missing_fields, contradictions.
Для каждого fields: key,label,value,unit,confidence,source_document,source_location,source_fragment,status.
Не выдумывай отсутствующие значения. Основные поля: object_type, area_m2, schedule,
contract_months, payment_delay_days, required_staff, sanitary_supplies_provider."""
    extraction = gateway.structured(task="extract_requirements",system=system,user=prompt_text,schema=DealExtraction)
    db.query(ExtractedField).filter(ExtractedField.deal_id==deal_id).delete()
    name_to_doc={d.filename:d.id for d in docs}
    for field in extraction.fields:
        db.add(ExtractedField(deal_id=deal_id,key=field.key,label=field.label,value=field.value,
                              unit=field.unit,status=field.status,confidence=field.confidence,
                              source_document_id=name_to_doc.get(field.source_document or ""),
                              source_location=field.source_location,source_fragment=field.source_fragment))
    db.commit()
    add_step(db,run,"ai_extraction","success",{"documents":len(docs)},
             extraction.model_dump(),duration_ms=int((time.perf_counter()-started)*1000))
    run.status="success"; run.finished_at=datetime.utcnow(); db.commit()
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
    result=calculate(req)
    calc=Calculation(deal_id=deal_id,input_json=req.model_dump_json(),
                     output_json=result.model_dump_json(),decision=result.decision)
    db.add(calc)
    deal=db.get(Deal,deal_id); deal.status="calculated"; db.commit(); db.refresh(calc)
    return {"calculation_id":calc.id,**result.model_dump()}

@app.get("/api/deals/{deal_id}/calculations")
def calculations(deal_id:int,db:Session=Depends(get_db)):
    rows=db.query(Calculation).filter(Calculation.deal_id==deal_id).order_by(Calculation.id.desc()).all()
    return [{"id":r.id,"created_at":r.created_at,"decision":r.decision,
             "input":json.loads(r.input_json),"output":json.loads(r.output_json)} for r in rows]
