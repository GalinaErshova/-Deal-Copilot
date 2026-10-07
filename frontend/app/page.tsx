"use client";

import {useEffect,useState} from "react";

const API=process.env.NEXT_PUBLIC_API_URL || "";

type Deal={id:number;title:string;status:string};
type Doc={id:number;filename:string;parser?:string;confidence?:string;status:string;warnings:string[]};
type Field={id:number;key:string;label:string;value:string|null;unit?:string;confidence?:number;status:string;source_document_id?:number;source_location?:string;source_fragment?:string;confirmed:boolean};
type Step={name:string;status:string;duration_ms?:number;input?:unknown;output?:unknown;warnings?:string[]};
type Run={id:number;status:string;steps:Step[]};
type Calc={calculation_id:number;labor_hours_month:number;fte:number;physical_staff:number;revenue_with_vat:number;revenue_net:number;direct_cost:number;full_cost:number;profit:number;margin:number;break_even_price_per_m2:number;target_price_per_m2:number;decision:string;conditions:string[];sensitivity:{delta:number;price:number;margin:number}[]};
type CalculationForm={area_m2:number;service_price_per_m2_month:number;productivity_m2_per_shift:number;monthly_hours_per_fte:number;hourly_staff_cost:number;replacement_coefficient:number;manager_monthly_cost:number;materials_per_m2_month:number;equipment_per_m2_month:number;logistics_monthly:number;overhead_rate:number;contingency_rate:number;target_margin:number;vat_rate:number;contract_months:number};
type AppSettings={calculation_defaults:CalculationForm;accepted_upload_extensions:string[];demo_mode:boolean;display_locale:string;currency_code:string;currency_unit_symbol:string;display_number_max_fraction_digits:number;display_currency_max_fraction_digits:number;display_percentage_factor:number;display_percentage_decimal_places:number;base_sensitivity_label:string;confidence_good_threshold:number;no_bid_margin_threshold:number;condition_price_decimal_places:number;condition_price_unit:string;sensitivity_bar_min_width:number;sensitivity_bar_max_width:number;sensitivity_bar_margin_offset:number;sensitivity_bar_scale:number};

const fmt=(n:number,locale:string,digits:number)=>new Intl.NumberFormat(locale,{maximumFractionDigits:digits}).format(n);
const money=(n:number,locale:string,currency:string,digits:number)=>new Intl.NumberFormat(locale,{style:"currency",currency,maximumFractionDigits:digits}).format(n);

export default function Home(){
  const [deal,setDeal]=useState<Deal|null>(null);
  const [appSettings,setAppSettings]=useState<AppSettings|null>(null);
  const [docs,setDocs]=useState<Doc[]>([]);
  const [fields,setFields]=useState<Field[]>([]);
  const [runs,setRuns]=useState<Run[]>([]);
  const [active,setActive]=useState("upload");
  const [busy,setBusy]=useState(false);
  const [selectedDoc,setSelectedDoc]=useState<number|null>(null);
  const [parsed,setParsed]=useState<any>(null);
  const [highlightPath,setHighlightPath]=useState<string|null>(null);
  const [calc,setCalc]=useState<Calc|null>(null);
  const [error,setError]=useState("");
  const [form,setForm]=useState<CalculationForm|null>(null);
  const [manualArea,setManualArea]=useState("");

  async function req(path:string, init?:RequestInit){
    if(!API) throw new Error("Настройте NEXT_PUBLIC_API_URL в frontend/.env.local");
    const r=await fetch(API+path,init);
    if(!r.ok) throw new Error(await r.text());
    return r.json();
  }
  async function refresh(){
    if(!deal)return;
    const all=await Promise.all([
      req("/deals/"+deal.id+"/documents"),
      req("/deals/"+deal.id+"/fields"),
      req("/deals/"+deal.id+"/pipeline")
    ]);
    setDocs(all[0]);setFields(all[1]);setRuns(all[2]);
  }
  useEffect(()=>{
    req("/settings").then((s:AppSettings)=>{setAppSettings(s);setForm(s.calculation_defaults)}).catch((e:any)=>setError(e.message));
  },[]);
  useEffect(()=>{if(deal)refresh().catch(()=>{})},[deal?.id]);

  async function createDeal(){
    setBusy(true);setError("");
    try{
      const d=await req("/deals?title="+encodeURIComponent("Демо: регулярный клининг офиса"),{method:"POST"});
      setDeal(d);setDocs([]);setFields([]);setRuns([]);setCalc(null);setActive("upload");
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }
  async function upload(files:FileList|null){
    if(!deal||!files||!files.length)return;
    const fd=new FormData();Array.from(files).forEach(f=>fd.append("files",f));
    setBusy(true);setError("");
    try{
      await req("/deals/"+deal.id+"/documents",{method:"POST",body:fd});
      await refresh();setActive("documents");
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }
  async function process(){
    if(!deal)return;
    setBusy(true);setError("");
    try{
      await req("/deals/"+deal.id+"/process",{method:"POST"});
      await refresh();setActive("review");
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }
  async function openDoc(id:number,path?:string){
    setSelectedDoc(id);
    setHighlightPath(path||null);
    setParsed(await req("/documents/"+id+"/parsed"));
    setActive("documents");
    if(path){
      setTimeout(()=>{
        const el=document.querySelector('[data-path="'+CSS.escape(path)+'"]');
        el?.scrollIntoView({behavior:"smooth",block:"center"});
      },120);
    }
  }
  async function saveField(row:Field,value:string){
    await req("/fields/"+row.id,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({value:value,confirmed:true})});
    if(row.key==="area_m2"){
      const numeric=Number(String(value).replace(",",".").replace(/[^0-9.\-]/g,""));
      if(Number.isFinite(numeric) && numeric>0) setForm(current=>current?({...current,area_m2:numeric}):current);
    }
    await refresh();
  }
  async function calculate(){
    if(!deal||!form)return;
    if(!criticalReady){setError("Подтвердите критическое поле «Площадь» перед расчётом.");setActive("review");return;}
    setBusy(true);setError("");
    try{
      const result=await req("/deals/"+deal.id+"/calculate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(form)});
      setCalc(result);setActive("economics");await refresh();
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }

  async function addManualArea(){
    if(!deal)return;
    const numeric=Number(manualArea.replace(",","."));
    if(!Number.isFinite(numeric)||numeric<=0){setError("Введите положительную площадь в м².");return;}
    setBusy(true);setError("");
    try{
      await req("/deals/"+deal.id+"/fields/area",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({value:numeric})});
      setForm(current=>current?({...current,area_m2:numeric}):current);
      setManualArea("");await refresh();
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }

  const tabs=[
    ["upload","Новая сделка"],["documents","Документы"],["review","Требования"],
    ["workforce","Трудоёмкость"],["economics","Экономика"],["decision","Решение"],["pipeline","Контроль"]
  ];
  const confirmed=fields.filter(x=>x.confirmed).length;
  const areaField=fields.find(x=>x.key==="area_m2");
  const criticalReady=Boolean(areaField?.confirmed && areaField.value && form);
  const statusClass=calc?.decision==="BID"?"good":calc?.decision==="NO BID"?"bad":"warn";

  return <main>
    <header className="top">
      <div><span className="brand">Deal Copilot</span><span className="badge">MVP 0–3</span></div>
      <div className="muted">{deal?("Сделка #"+deal.id+" · "+deal.status):"Сделка не создана"}</div>
    </header>

    {appSettings?.demo_mode&&<div className="warning">Демо-режим: извлечение использует настроенную заглушку модели, а результаты нужно сверять с документами.</div>}

    <section className="hero">
      <div>
        <p className="eyebrow">AI читает документы · алгоритм считает деньги</p>
        <h1>Коммерческий расчёт под полным пошаговым контролем</h1>
        <p>Демо B2B-клининга: от тендерных файлов до трудоёмкости, маржи и решения BID / NO BID.</p>
      </div>
      <div className="heroStats">
        <div><b>{docs.length}</b><span>документов</span></div>
        <div><b>{fields.length}</b><span>параметров</span></div>
        <div><b>{confirmed}</b><span>подтверждено</span></div>
      </div>
    </section>

    {error&&<div className="error">{error}</div>}

    <nav className="tabs">
      {tabs.map(function(t){return <button key={t[0]} className={active===t[0]?"active":""} onClick={()=>setActive(t[0])}>{t[1]}</button>})}
    </nav>

    {active==="upload"&&<section className="panel two">
      <div>
        <h2>1. Создать демо-сделку</h2>
        <p className="muted">Одна компания, один пользователь. Для MVP этого достаточно.</p>
        <button className="primary" disabled={busy} onClick={createDeal}>{deal?"Создать новую сделку":"Создать сделку"}</button>
      </div>
      <div>
        <h2>2. Загрузить документы</h2>
        <label className={"drop "+(!deal?"disabled":"")}>
          <input type="file" multiple accept={appSettings?.accepted_upload_extensions.join(",")} disabled={!deal||busy||!appSettings} onChange={e=>upload(e.target.files)}/>
          <b>{appSettings?.accepted_upload_extensions.map((ext)=>ext.replace(".","").toUpperCase()).join(" · ")}</b><span>выберите один или несколько файлов</span>
        </label>
      </div>
    </section>}

    {active==="documents"&&<section className="panel">
      <div className="sectionHead">
        <div><h2>Сверка документов</h2><p className="muted">Оригинал слева, структурированный результат справа — механика Ask-Learn.</p></div>
        <button disabled={!docs.length||busy} onClick={process}>Распознать и извлечь требования</button>
      </div>
      <div className="docList">
        {docs.map(d=><button key={d.id} onClick={()=>openDoc(d.id)} className={selectedDoc===d.id?"selected":""}><span>{d.filename}</span><small>{(d.parser||"—")+" · "+(d.confidence||"—")+" · "+d.status}</small></button>)}
      </div>
      {selectedDoc&&<div className="split">
        <article><h3>Оригинал</h3><iframe title="original" src={API+"/documents/"+selectedDoc+"/original"}/></article>
        <article><h3>Результат парсинга</h3><div className="parsed">
          {parsed?.warnings?.map((w:string)=><div className="warning" key={w}>{w}</div>)}
          {parsed?.blocks?.map((b:any,i:number)=><div data-path={b.path} className={"block "+(highlightPath===b.path?"highlighted":"")} key={i}><small>{(b.page_no?("стр. "+b.page_no+" · "):"")+b.path}</small>{b.title&&<b>{b.title}</b>}<p>{b.text}</p></div>)}
        </div></article>
      </div>}
    </section>}

    {active==="review"&&<section className="panel">
      <div className="sectionHead">
        <div><h2>Карточка требований</h2><p className="muted">Поля проверяются по источнику и подтверждаются пользователем.</p></div>
        <button disabled={!criticalReady} onClick={()=>setActive("workforce")}>{criticalReady?"К расчёту →":"Подтвердите площадь"}</button>
      </div>
      <div className="fields">
        {!areaField&&<div className="field">
          <div className="fieldMeta"><b>Площадь объекта, м²</b><span className="confidence warn">Источник не найден</span></div>
          <div className="fieldInput"><input type="number" min="0" step="any" value={manualArea} onChange={e=>setManualArea(e.target.value)} placeholder="Введите площадь вручную"/><span>м²</span><button disabled={busy||!manualArea} onClick={addManualArea}>Добавить на подтверждение</button></div>
          <p className="muted">Расчёт станет доступен после отдельного подтверждения этого значения.</p>
        </div>}
        {fields.map(f=><div className="field" key={f.id}>
          <div className="fieldMeta"><b>{f.label}</b><span className={"confidence "+(appSettings&&((f.confidence||0)>appSettings.confidence_good_threshold)?"good":"warn")}>{f.confidence?(appSettings?Math.round(f.confidence*appSettings.display_percentage_factor)+"%":f.confidence):"—"}</span></div>
          <div className="fieldInput">
            <input defaultValue={f.value||""} onBlur={e=>{if(e.target.value!==f.value)saveField(f,e.target.value)}}/>
            <span>{f.unit}</span>
            <button className={f.confirmed?"confirmed":""} onClick={()=>saveField(f,f.value||"")}>{f.confirmed?"✓ Подтверждено":"Подтвердить"}</button>
          </div>
          <details><summary>Источник</summary><p>{f.source_location||"Источник не указан"}</p><blockquote>{f.source_fragment||"Фрагмент будет доступен при реальном AI extraction."}</blockquote>{f.source_document_id&&<button onClick={()=>openDoc(f.source_document_id as number,(f.source_location||"").split(" ")[0])}>Открыть источник в сверке →</button>}</details>
        </div>)}
      </div>
    </section>}

    {active==="workforce"&&<section className="panel two">
      <div>
        <h2>Параметры расчёта</h2>
        {form&&[
          ["area_m2","Площадь, м²"],["productivity_m2_per_shift","Выработка, м²/смену"],
          ["monthly_hours_per_fte","Фонд времени, ч/мес"],["hourly_staff_cost",`Стоимость часа, ${appSettings?.currency_unit_symbol??""}`],
          ["replacement_coefficient","Коэффициент замещения"]
        ].map(function(x){const k=x[0] as keyof CalculationForm;return <label className="control" key={k}><span>{x[1]}</span><input type="number" step="any" value={form[k]} onChange={e=>setForm(current=>current?({...current,[k]:Number(e.target.value)}):current)}/></label>})}
        <button className="primary" disabled={!criticalReady} onClick={calculate}>Рассчитать трудоёмкость и экономику</button>
        {!form&&<p className="empty">Загрузка настроек расчёта…</p>}
        {!criticalReady&&<p className="warning">Расчёт заблокирован: подтвердите площадь в карточке требований.</p>}
      </div>
      <div className="calcPreview">
        <h2>Логика MVP-1</h2>
        <div className="formula">Площадь ÷ выработка × смены → человеко-часы → FTE → физическая численность</div>
        {calc&&appSettings&&<><div className="bigMetric"><b>{fmt(calc.labor_hours_month,appSettings.display_locale,appSettings.display_number_max_fraction_digits)}</b><span>чел.-часов / мес.</span></div><div className="metrics"><div><b>{fmt(calc.fte,appSettings.display_locale,appSettings.display_number_max_fraction_digits)}</b><span>FTE</span></div><div><b>{calc.physical_staff}</b><span>физ. сотрудников</span></div></div></>}
      </div>
    </section>}

    {active==="economics"&&<section className="panel">
      <div className="sectionHead"><div><h2>Экономика контракта</h2><p className="muted">Все показатели считает детерминированный Python-модуль.</p></div><button onClick={()=>setActive("decision")}>К решению →</button></div>
      <div className="economicsGrid">
        <div className="controls">
          {[
            ["service_price_per_m2_month",`Тариф, ${appSettings?.currency_unit_symbol??""}/м²/мес`],["materials_per_m2_month",`Материалы, ${appSettings?.currency_unit_symbol??""}/м²/мес`],
            ["equipment_per_m2_month",`Техника, ${appSettings?.currency_unit_symbol??""}/м²/мес`],["manager_monthly_cost",`Управление, ${appSettings?.currency_unit_symbol??""}/мес`],
            ["logistics_monthly",`Логистика, ${appSettings?.currency_unit_symbol??""}/мес`],["target_margin","Целевая маржа"]
          ].map(function(x){const k=x[0] as keyof CalculationForm;return form?<label className="control" key={k}><span>{x[1]}</span><input type="number" step="any" value={form[k]} onChange={e=>setForm(current=>current?({...current,[k]:Number(e.target.value)}):current)}/></label>:null})}
          <button onClick={calculate}>Пересчитать</button>
        </div>
        {calc?<div className="kpis">
          <div><span>Выручка без НДС</span><b>{appSettings?money(calc.revenue_net,appSettings.display_locale,appSettings.currency_code,appSettings.display_currency_max_fraction_digits):calc.revenue_net}</b></div>
          <div><span>Полная себестоимость</span><b>{appSettings?money(calc.full_cost,appSettings.display_locale,appSettings.currency_code,appSettings.display_currency_max_fraction_digits):calc.full_cost}</b></div>
          <div><span>Прибыль</span><b>{appSettings?money(calc.profit,appSettings.display_locale,appSettings.currency_code,appSettings.display_currency_max_fraction_digits):calc.profit}</b></div>
          <div><span>Маржа</span><b className={appSettings&&calc.margin<appSettings.no_bid_margin_threshold?"badText":calc.margin<(form?.target_margin??calc.margin)?"warnText":"goodText"}>{appSettings?((calc.margin*appSettings.display_percentage_factor).toFixed(appSettings.display_percentage_decimal_places)+"%"):calc.margin}</b></div>
          <div><span>Break-even</span><b>{appSettings?fmt(calc.break_even_price_per_m2,appSettings.display_locale,appSettings.display_number_max_fraction_digits)+" "+appSettings.currency_unit_symbol+"/м²":calc.break_even_price_per_m2}</b></div>
          <div><span>Тариф для цели</span><b>{appSettings?fmt(calc.target_price_per_m2,appSettings.display_locale,appSettings.display_number_max_fraction_digits)+" "+appSettings.currency_unit_symbol+"/м²":calc.target_price_per_m2}</b></div>
        </div>:<div className="empty">Запустите расчёт на вкладке «Трудоёмкость».</div>}
      </div>
      {calc&&appSettings&&<div className="sensitivity"><h3>Чувствительность к цене</h3>{calc.sensitivity.map(s=><div key={s.delta} className="sens"><span>{s.delta===0?appSettings.base_sensitivity_label:((s.delta>0?"+":"")+Math.round(s.delta*appSettings.display_percentage_factor)+"%")}</span><i style={{width:String(Math.max(appSettings.sensitivity_bar_min_width,Math.min(appSettings.sensitivity_bar_max_width,(s.margin+appSettings.sensitivity_bar_margin_offset)*appSettings.sensitivity_bar_scale))+"%")}}></i><b>{(s.margin*appSettings.display_percentage_factor).toFixed(appSettings.display_percentage_decimal_places)+"%"}</b></div>)}</div>}
    </section>}

    {active==="decision"&&<section className="panel decision">
      <h2>Коммерческое решение</h2>
      {calc?<><div className={"decisionHero "+statusClass}><span>Решение системы</span><b>{calc.decision}</b></div>{calc.conditions.length>0&&<div className="conditions"><h3>Условия</h3>{calc.conditions.map(c=><p key={c}>• {c}</p>)}</div>}<p className="muted">LLM может объяснять решение, но статус задаётся правилами расчётного модуля.</p></>:<div className="empty">Сначала выполните расчёт.</div>}
    </section>}

    {active==="pipeline"&&<section className="panel">
      <h2>Пошаговый контроль обработки</h2>
      <p className="muted">Для каждого шага доступны вход, выход, длительность и предупреждения.</p>
      {runs.length===0?<div className="empty">Пока нет запусков.</div>:runs.map(run=><div className="run" key={run.id}><h3>{"Запуск #"+run.id+" · "+run.status}</h3>{run.steps.map((s,i)=><details className={"step "+s.status} key={i}><summary><span>{(s.status==="success"?"✓":s.status==="failed"?"✕":"○")+" "+s.name}</span><small>{s.duration_ms?String(s.duration_ms)+" ms":""}</small></summary><div className="stepBody">{s.warnings?.map(w=><p className="warning" key={w}>{w}</p>)}<div className="json"><b>Вход</b><pre>{JSON.stringify(s.input,null,2)}</pre></div><div className="json"><b>Выход</b><pre>{JSON.stringify(s.output,null,2)}</pre></div></div></details>)}</div>)}
    </section>}
  </main>
}
