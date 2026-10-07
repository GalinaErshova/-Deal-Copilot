"use client";

import {useEffect,useState,type ReactNode} from "react";

const API=process.env.NEXT_PUBLIC_API_URL || "";

type Deal={id:number;title:string;status:string;document_count?:number};
type Doc={id:number;filename:string;parser?:string;confidence?:string;status:string;warnings:string[]};
type Field={id:number;key:string;label:string;value:string|null;unit?:string;confidence?:number;status:string;source_document_id?:number;source_location?:string;source_fragment?:string;confirmed:boolean};
type Step={name:string;status:string;duration_ms?:number;input?:unknown;output?:unknown;warnings?:string[]};
type Run={id:number;status:string;steps:Step[]};
type ParsedBlock={kind:string;text:string;path:string;page_no?:number;title?:string;rows?:string[][]};
type ParsedDocument={parser:string;blocks:ParsedBlock[];warnings?:string[]};
type ProcessProgress={value:number;label:string};
type ScheduleMode="daily"|"weekly"|"monthly"|"on_request"|"custom"|"unspecified";
type AreaComponent={id:string;address:string;area_type:string;work_type:string;work_type_source_document_id:number|null;work_type_source_location:string;work_type_source_fragment:string;area_m2:number;source_document_id:number;source_document_name:string;source_location:string;source_fragment:string;schedule_mode:ScheduleMode;schedule_label:string;schedule_status:string;schedule_warnings:string[];schedule_source_document_id:number|null;schedule_source_document_name:string|null;schedule_source_location:string;schedule_source_fragment:string;schedule_additional_frequencies?:string[];curation_status?:string;curation_warnings?:string[];productivity_m2_per_shift:number|null;productivity_reference?:{id:number;name:string;unit:string;value:number;notes:string|null}|null;shifts_per_month:number|null;labor_hours_month?:number;fte?:number;physical_staff?:number};
type Calc={calculation_id:number;labor_hours_month:number;fte:number;physical_staff:number;physical_staff_by_site?:number;total_area_m2?:number;components?:AreaComponent[];revenue_with_vat:number;revenue_net:number;direct_cost:number;full_cost:number;profit:number;margin:number;break_even_price_per_m2:number;target_price_per_m2:number;decision:string;conditions:string[];sensitivity:{delta:number;price:number;margin:number}[]};
type CalculationForm={area_m2:number;service_price_per_m2_month:number;productivity_m2_per_shift:number;monthly_hours_per_fte:number;hourly_staff_cost:number;replacement_coefficient:number;manager_monthly_cost:number;materials_per_m2_month:number;equipment_per_m2_month:number;logistics_monthly:number;overhead_rate:number;contingency_rate:number;target_margin:number;vat_rate:number;contract_months:number};
type AppSettings={calculation_defaults:CalculationForm;working_days_per_month:number;working_days_per_week:number;monthly_frequency_shifts:number;hours_per_shift:number;accepted_upload_extensions:string[];demo_mode:boolean;llm_provider:string;display_locale:string;currency_code:string;currency_unit_symbol:string;display_number_max_fraction_digits:number;display_currency_max_fraction_digits:number;display_percentage_factor:number;display_percentage_decimal_places:number;base_sensitivity_label:string;confidence_good_threshold:number;no_bid_margin_threshold:number;condition_price_decimal_places:number;condition_price_unit:string;sensitivity_bar_min_width:number;sensitivity_bar_max_width:number;sensitivity_bar_margin_offset:number;sensitivity_bar_scale:number};

const fmt=(n:number,locale:string,digits:number)=>new Intl.NumberFormat(locale,{maximumFractionDigits:digits}).format(n);
const money=(n:number,locale:string,currency:string,digits:number)=>new Intl.NumberFormat(locale,{style:"currency",currency,maximumFractionDigits:digits}).format(n);
const shiftsForMode=(mode:ScheduleMode,settings:AppSettings|null):number|null=>{
  if(!settings)return null;
  if(mode==="daily")return settings.working_days_per_month;
  if(mode==="weekly")return settings.working_days_per_month/settings.working_days_per_week;
  if(mode==="monthly")return settings.monthly_frequency_shifts;
  return null;
};
const scheduleCountHint=(mode:ScheduleMode,settings:AppSettings|null):string=>{
  if(!settings)return "";
  if(mode==="daily")return `Из настройки: ${settings.working_days_per_month} рабочих дней в месяц.`;
  if(mode==="weekly")return `${settings.working_days_per_month} рабочих дней ÷ ${settings.working_days_per_week} дней в неделе = ${fmt(settings.working_days_per_month/settings.working_days_per_week,"ru-RU",1)} смены в среднем за месяц.`;
  if(mode==="monthly")return `${settings.monthly_frequency_shifts} смена за месяц по настройке.`;
  return "Количество нужно указать вручную.";
};

function productivityEstimate(component:AreaComponent,settings:AppSettings|null,monthlyHoursPerFte:number){
  const rate=component.productivity_m2_per_shift||0;
  if(!settings||rate<=0)return null;
  const employeeShiftsPerVisit=component.area_m2/rate;
  const hoursPerVisit=employeeShiftsPerVisit*settings.hours_per_shift;
  const monthlyVisits=shiftsForMode(component.schedule_mode,settings)??component.shifts_per_month;
  const hoursPerMonth=monthlyVisits&&monthlyVisits>0?hoursPerVisit*monthlyVisits:null;
  return {rate,employeeShiftsPerVisit,hoursPerVisit,monthlyVisits,hoursPerMonth,fte:hoursPerMonth&&monthlyHoursPerFte>0?hoursPerMonth/monthlyHoursPerFte:null};
}

function evidenceText(text:string,fragments:string[]){
  let parts:ReactNode[]=[text];
  fragments.filter(Boolean).forEach((fragment,index)=>{
    const next:React.ReactNode[]=[];
    parts.forEach((part,partIndex)=>{
      if(typeof part!=="string"){next.push(part);return;}
      const start=part.toLocaleLowerCase().indexOf(fragment.toLocaleLowerCase());
      if(start<0){next.push(part);return;}
      next.push(part.slice(0,start),<mark key={`${index}-${partIndex}`}>{part.slice(start,start+fragment.length)}</mark>,part.slice(start+fragment.length));
    });
    parts=next;
  });
  return parts;
}

// Переводит технический путь блока в понятное место документа для карточки требования.
function sourceLocationLabel(location:string|undefined,parser:string|undefined){
  if(!location)return "Место в документе не указано";
  const path=location.split(/\s+page\s+/i)[0];
  const page=location.match(/\bpage\s+(\d+)/i)?.[1];
  const paragraph=path.match(/\/p\/(\d+)/)?.[1];
  const table=path.match(/\/table\/(\d+)/)?.[1];
  const sheet=path.match(/\/sheet\/(\d+)/)?.[1];
  const slide=path.match(/\/slide\/(\d+)/)?.[1];
  const block=paragraph?`Абзац ${paragraph}`:table?`Таблица ${table}`:sheet?`Лист ${sheet}`:slide?`Слайд ${slide}`:null;
  const pageLabel=page?`${parser==="pptx"?"Слайд":"Страница"} ${page}`:null;
  return [pageLabel,block].filter(Boolean).join(" · ")||"Фрагмент документа";
}

// Находит полное предложение или строку таблицы, где расположен проверенный фрагмент.
function fullEvidenceQuote(parsed:ParsedDocument|undefined,location:string|undefined,fragment:string|undefined){
  if(!fragment)return "Цитата не указана";
  const path=location?.split(/\s+page\s+/i)[0];
  const text=parsed?.blocks?.find(block=>block.path===path)?.text?.trim();
  if(!text)return fragment;
  const normalize=(value:string)=>value.replace(/\s+/g," ").trim().toLocaleLowerCase();
  const normalizedFragment=normalize(fragment);
  const sentence=text.split(/\n+|(?<=[.!?])\s+(?=[А-ЯЁA-Z«"(\d])/u)
    .find(part=>normalize(part).includes(normalizedFragment));
  return sentence?.trim()||(normalize(text).includes(normalizedFragment)?text:fragment);
}

function documentTable(rows:string[][]){
  if(!rows?.length)return null;
  return <div className="tablePreview"><table><tbody>{rows.map((row,rowIndex)=><tr key={rowIndex}>{row.map((cell,cellIndex)=>rowIndex===0
    ?<th key={cellIndex}>{cell||`Столбец ${cellIndex+1}`}</th>
    :<td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table></div>;
}

export default function Home(){
  const [deal,setDeal]=useState<Deal|null>(null);
  const [appSettings,setAppSettings]=useState<AppSettings|null>(null);
  const [docs,setDocs]=useState<Doc[]>([]);
  const [fields,setFields]=useState<Field[]>([]);
  const [areaComponents,setAreaComponents]=useState<AreaComponent[]>([]);
  const [runs,setRuns]=useState<Run[]>([]);
  const [active,setActive]=useState("upload");
  const [busy,setBusy]=useState(false);
  const [selectedDoc,setSelectedDoc]=useState<number|null>(null);
  const [parsed,setParsed]=useState<any>(null);
  // Кэш распознанных блоков для быстрого показа полной цитаты в карточках требований.
  const [sourceParsed,setSourceParsed]=useState<Record<number,ParsedDocument>>({});
  const [highlightPath,setHighlightPath]=useState<string|null>(null);
  const [processProgress,setProcessProgress]=useState<ProcessProgress|null>(null);
  const [calc,setCalc]=useState<Calc|null>(null);
  const [calculationDirty,setCalculationDirty]=useState(false);
  const [calculationConfirmed,setCalculationConfirmed]=useState(false);
  const [error,setError]=useState("");
  const [form,setForm]=useState<CalculationForm|null>(null);
  const [manualArea,setManualArea]=useState("");
  const [productivityHelp,setProductivityHelp]=useState<AreaComponent|null>(null);

  async function req(path:string, init?:RequestInit){
    if(!API) throw new Error("Настройте NEXT_PUBLIC_API_URL в frontend/.env.local");
    const r=await fetch(API+path,init);
    if(!r.ok){
      const body=await r.json().catch(()=>null);
      throw new Error(body?.detail||body?.message||`Ошибка запроса (${r.status})`);
    }
    return r.json();
  }
  async function refresh(){
    if(!deal)return;
    const all=await Promise.all([
      req("/deals/"+deal.id+"/documents"),
      req("/deals/"+deal.id+"/fields"),
      req("/deals/"+deal.id+"/pipeline"),
      req("/deals/"+deal.id+"/area-components")
    ]);
    setDocs(all[0]);setFields(all[1]);setRuns(all[2]);
    setAreaComponents((current:AreaComponent[])=>all[3].map((source:AreaComponent)=>{
      const previous=current.find(item=>item.id===source.id);
      return {...source,area_m2:previous?.area_m2??source.area_m2,
        productivity_m2_per_shift:previous?.productivity_m2_per_shift??source.productivity_m2_per_shift,
        schedule_mode:previous?.schedule_mode??source.schedule_mode,
        shifts_per_month:previous?.shifts_per_month??source.shifts_per_month};
    }));
  }
  useEffect(()=>{
    Promise.all([req("/settings"),req("/deals")]).then(([s,deals]:[AppSettings,Deal[]])=>{
      setAppSettings(s);setForm(s.calculation_defaults);
      const savedId=Number(window.localStorage.getItem("dealCopilot.activeDealId"));
      const selected=deals.find(d=>d.id===savedId)||deals.find(d=>(d.document_count||0)>0)||deals[0];
      if(selected){
        window.localStorage.setItem("dealCopilot.activeDealId",String(selected.id));
        setDeal(selected);setActive((selected.document_count||0)>0?"documents":"upload");
      }
    }).catch((e:any)=>setError(e.message));
  },[]);
  useEffect(()=>{if(deal)refresh().catch(()=>{})},[deal?.id]);
  useEffect(()=>{
    const total=areaComponents.reduce((sum,component)=>sum+component.area_m2,0);
    if(total>0)setForm(current=>current&&current.area_m2!==total?({...current,area_m2:total}):current);
  },[areaComponents,appSettings]);
  useEffect(()=>{
    const documentIds=[...new Set(fields.map(field=>field.source_document_id).filter((id):id is number=>Boolean(id)))].filter(id=>!sourceParsed[id]);
    if(!documentIds.length)return;
    let cancelled=false;
    Promise.all(documentIds.map(async id=>[id,await req("/documents/"+id+"/parsed")] as const))
      .then(entries=>{if(!cancelled&&entries.length)setSourceParsed(current=>({...current,...Object.fromEntries(entries)}))})
      .catch(()=>{});
    return()=>{cancelled=true};
  },[fields,sourceParsed]);

  async function createDeal(){
    setBusy(true);setError("");
    try{
      const d=await req("/deals?title="+encodeURIComponent("Демо: регулярный клининг офиса"),{method:"POST"});
      window.localStorage.setItem("dealCopilot.activeDealId",String(d.id));
      setDeal(d);setDocs([]);setFields([]);setRuns([]);setAreaComponents([]);setCalc(null);setCalculationDirty(false);setCalculationConfirmed(false);setActive("upload");
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }
  async function upload(files:FileList|null){
    if(!deal||!files||!files.length)return;
    const fd=new FormData();Array.from(files).forEach(f=>fd.append("files",f));
    setBusy(true);setError("");
    try{
      await req("/deals/"+deal.id+"/documents",{method:"POST",body:fd});
      window.localStorage.setItem("dealCopilot.activeDealId",String(deal.id));
      await refresh();setActive("documents");
    }catch(e:any){setError(e.message);await refresh().catch(()=>{})}finally{setBusy(false)}
  }
  async function process(){
    if(!deal)return;
    setCalculationConfirmed(false);setCalc(null);setCalculationDirty(false);
    setBusy(true);setError("");
    const previousRunId=Math.max(0,...runs.map(run=>run.id));
    let stopPolling=false;
    setProcessProgress({value:4,label:"Подключаем обработку документов…"});
    const progressPolling=(async()=>{
      while(!stopPolling){
        try{
          const currentRuns:Run[]=await req("/deals/"+deal.id+"/pipeline");
          setRuns(currentRuns);
          const currentRun=currentRuns.find(run=>run.id>previousRunId);
          if(currentRun){
            const parseSteps=currentRun.steps.filter(step=>step.name.startsWith("parse:"));
            const finished=parseSteps.filter(step=>step.status==="success"||step.status==="failed").length;
            const parsedCount=parseSteps.filter(step=>step.status==="success").length;
            const parseProgress=docs.length?Math.round(finished/docs.length*76):0;
            if(currentRun.status==="success"){
              setProcessProgress({value:100,label:"Требования извлечены"});return;
            }
            if(currentRun.status==="failed"){
              setProcessProgress({value:Math.max(8,8+parseProgress),label:"Обработка завершилась с ошибкой"});return;
            }
            if(finished>=docs.length){
              setProcessProgress({value:88,label:"Документы разобраны. Модель извлекает требования…"});
            }else{
              setProcessProgress({value:Math.max(8,8+parseProgress),label:`Разобрано документов: ${parsedCount} из ${docs.length}`});
            }
          }
        }catch{/* Основной запрос покажет ошибку, если обработка завершится неудачно. */}
        await new Promise(resolve=>window.setTimeout(resolve,800));
      }
    })();
    try{
      await req("/deals/"+deal.id+"/process",{method:"POST"});
      stopPolling=true;await progressPolling;
      setProcessProgress({value:100,label:"Требования извлечены"});
      await refresh();setActive("review");
    }catch(e:any){stopPolling=true;await progressPolling;setProcessProgress(null);setError(e.message);await refresh().catch(()=>{});setActive("documents")}finally{stopPolling=true;setBusy(false);window.setTimeout(()=>setProcessProgress(null),1200)}
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
    setCalculationConfirmed(false);setCalc(null);setCalculationDirty(false);
    await refresh();
  }
  async function calculate(){
    if(!deal||!form)return;
    if(!calculationInputsReady){setError(areaComponents.length?"Заполните выработку и режим уборки для каждой строки. Если график задан заявками, укажите ожидаемые выезды в месяц.":"Подтвердите критическое поле «Площадь» перед расчётом.");setActive(areaComponents.length?"workforce":"review");return;}
    if(!calculationConfirmed){setError("Подтвердите расчёт целиком на вкладке «Трудоёмкость».");setActive("workforce");return;}
    setBusy(true);setError("");
    try{
      const path=areaComponents.length?"/calculate-breakdown":"/calculate";
      const body=areaComponents.length?{confirmed:calculationConfirmed,assumptions:form,components:areaComponents.map(({id,area_m2,productivity_m2_per_shift,schedule_mode,shifts_per_month})=>({id,area_m2,productivity_m2_per_shift,schedule_mode,shifts_per_month}))}:form;
      const result=await req("/deals/"+deal.id+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
      setCalc(result);setCalculationDirty(false);setActive("economics");await refresh();
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }

  function updateAreaComponent(id:string,patch:Partial<AreaComponent>){
    setAreaComponents(current=>current.map(component=>component.id===id?({...component,...patch}):component));
    setCalculationConfirmed(false);
    setCalc(null);setCalculationDirty(false);
  }

  function updateScheduleMode(id:string,mode:ScheduleMode){
    updateAreaComponent(id,{schedule_mode:mode,shifts_per_month:shiftsForMode(mode,appSettings)});
  }

  function updateCalculationValue(key:keyof CalculationForm,value:number,preserveConfirmation=false){
    setForm(current=>current?({...current,[key]:value}):current);
    setError("");
    if(preserveConfirmation){setCalculationDirty(true);return;}
    setCalculationConfirmed(false);setCalc(null);setCalculationDirty(false);
  }

  async function addManualArea(){
    if(!deal)return;
    const numeric=Number(manualArea.replace(",","."));
    if(!Number.isFinite(numeric)||numeric<=0){setError("Введите положительную площадь в м².");return;}
    setBusy(true);setError("");
    try{
      await req("/deals/"+deal.id+"/fields/area",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({value:numeric})});
      setForm(current=>current?({...current,area_m2:numeric}):current);
      setCalculationConfirmed(false);setCalc(null);setCalculationDirty(false);
      setManualArea("");await refresh();
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }

  const tabs=[
    {key:"upload",label:"Новая сделка",title:"Рабочее пространство",description:"Создайте сделку и загрузите тендерные материалы."},
    {key:"documents",label:"Документы",title:"Документы",description:"Сопоставьте оригинал файла с результатом разбора."},
    {key:"review",label:"Требования",title:"Проверка требований",description:"Проверьте извлечённые значения и подтвердите исходные данные."},
    {key:"workforce",label:"Трудоёмкость",title:"Расчёт трудоёмкости",description:"Настройте параметры объекта и проверьте потребность в персонале."},
    {key:"economics",label:"Экономика",title:"Экономика контракта",description:"Оцените себестоимость, маржу и чувствительность к тарифу."},
    {key:"decision",label:"Решение",title:"Коммерческое решение",description:"Посмотрите итог BID / BID WITH CONDITIONS / NO BID."},
    {key:"pipeline",label:"Контроль",title:"Контроль обработки",description:"Проверьте входы, результаты и предупреждения каждого этапа."},
  ];
  const currentTab=tabs.find(tab=>tab.key===active)??tabs[0];
  const productivityHelpNumbers=productivityHelp?productivityEstimate(productivityHelp,appSettings,form?.monthly_hours_per_fte??0):null;
  const confirmed=fields.filter(x=>x.confirmed).length;
  const areaField=fields.find(x=>x.key==="area_m2");
  const areaBreakdownReady=areaComponents.length>0&&areaComponents.every(component=>Boolean(
    component.curation_status==="verified"&&component.schedule_status!=="needs_review"&&component.area_m2>0
    &&(component.productivity_m2_per_shift||0)>0
    &&((shiftsForMode(component.schedule_mode,appSettings)??component.shifts_per_month)||0)>0
  ));
  const calculationInputsReady=Boolean(form&&(areaComponents.length?areaBreakdownReady:areaField?.confirmed&&areaField.value));
  const criticalReady=Boolean(calculationInputsReady&&calculationConfirmed);
  const statusClass=calc?.decision==="BID"?"good":calc?.decision==="NO BID"?"bad":"warn";

  return <div className="appShell">
    <aside className="sidebar">
      <div className="sidebarBrand">
        <div className="brandMark" aria-hidden="true">DC</div>
        <div><span className="brand">Deal Copilot</span><span className="badge">MVP 0–3</span></div>
      </div>

      <section className="sidebarDeal" aria-label="Текущая сделка">
        <span className="sidebarLabel">АКТИВНАЯ СДЕЛКА</span>
        <strong>{deal?("Сделка #"+deal.id):"Сделка не создана"}</strong>
        <span className={"dealStatus "+(deal?"online":"idle")}><i/> {deal?deal.status:"Создайте сделку, чтобы начать"}</span>
      </section>

      <section className="sidebarStats" aria-label="Сводка по сделке">
        <div><b>{docs.length}</b><span>документов</span></div>
        <div><b>{fields.length}</b><span>параметров</span></div>
        <div><b>{confirmed}</b><span>подтверждено</span></div>
      </section>

      <nav className="sideNav" aria-label="Рабочие разделы">
        <span className="sidebarLabel">РАБОЧИЙ ПРОЦЕСС</span>
        {tabs.map((tab,index)=><button key={tab.key} className={active===tab.key?"active":""} aria-current={active===tab.key?"page":undefined} onClick={()=>setActive(tab.key)}>
          <span className="navIndex">{String(index+1).padStart(2,"0")}</span><span>{tab.label}</span><span className="navArrow" aria-hidden="true">→</span>
        </button>)}
      </nav>

      <footer className="sidebarFooter">
        <span className={"modeDot "+(appSettings?.demo_mode?"demo":"live")}/>
        <span>{appSettings?.demo_mode?"Тестовый режим":appSettings?.llm_provider==="local"?"MiMo · локально":"MiMo · API"}</span>
      </footer>
    </aside>

    <main className="workspace">
      <header className="workspaceHeader">
        <div>
          <p className="workspaceEyebrow">DEAL COPILOT <span>/</span> {deal?("СДЕЛКА #"+deal.id):"НОВЫЙ ПРОЕКТ"}</p>
          <h1>{currentTab.title}</h1>
          <p>{currentTab.description}</p>
        </div>
        <div className="workspaceStep"><span>ШАГ</span><b>{String(tabs.findIndex(tab=>tab.key===active)+1).padStart(2,"0")}</b><i>/</i><span>{String(tabs.length).padStart(2,"0")}</span></div>
      </header>

      {appSettings?.demo_mode&&<div className="demoNotice"><span className="noticeIcon">i</span><span>Тестовый режим: извлечение использует заглушку, сверяйте требования с документами.</span></div>}
      {error&&<div className="error" role="alert">{error}</div>}

      <div className="workspaceContent">
    {active==="upload"&&<section className="panel two">
      <div>
        <h2><span className="panelStep">01</span>Создать сделку</h2>
        <p className="muted">Одна компания, один пользователь. Для MVP этого достаточно.</p>
        <button className="primary" disabled={busy} onClick={createDeal}>{deal?"Создать новую сделку":"Создать сделку"}</button>
      </div>
      <div>
        <h2><span className="panelStep">02</span>Загрузить документы</h2>
        <label className={"drop "+(!deal?"disabled":"")}>
          <input type="file" multiple accept={appSettings?.accepted_upload_extensions.join(",")} disabled={!deal||busy||!appSettings} onChange={e=>upload(e.target.files)}/>
          <b>{appSettings?.accepted_upload_extensions.map((ext)=>ext.replace(".","").toUpperCase()).join(" · ")}</b><span>выберите один или несколько файлов</span>
        </label>
      </div>
    </section>}

    {active==="documents"&&<section className="panel">
      <div className="sectionHead">
        <div><h2>Сверка документов</h2><p className="muted">Предпросмотр документа слева, распознанные блоки справа; проверенные цитаты подсвечены.</p></div>
        <button disabled={!docs.length||busy} onClick={process}>Распознать и извлечь требования</button>
      </div>
      {processProgress&&<div className="processingProgress" role="status" aria-live="polite">
        <div className="progressLabel"><span>{processProgress.label}</span><b>{processProgress.value}%</b></div>
        <div className="progressTrack" role="progressbar" aria-label="Ход обработки документов" aria-valuemin={0} aria-valuemax={100} aria-valuenow={processProgress.value} aria-valuetext={processProgress.label}>
          <span style={{width:`${processProgress.value}%`}}/>
        </div>
      </div>}
      <div className="docList">
        {docs.map(d=><button key={d.id} onClick={()=>openDoc(d.id)} className={selectedDoc===d.id?"selected":""}><span>{d.filename}</span><small>{(d.parser||"—")+" · "+(d.confidence||"—")+" · "+d.status}</small></button>)}
      </div>
      {selectedDoc&&<div className="split">
        <article><h3>Документ</h3><a className="downloadOriginal" href={API+"/documents/"+selectedDoc+"/original"} download={docs.find(d=>d.id===selectedDoc)?.filename}>Скачать исходный файл ↗</a>
          {docs.find(d=>d.id===selectedDoc)?.filename.toLowerCase().endsWith(".pdf")
            ?<iframe className="originalPreview" title="Исходный PDF" src={API+"/documents/"+selectedDoc+"/original"}/>
            :<div className="parsed documentPreview">
              {parsed?.blocks?.length?parsed.blocks.map((b:ParsedBlock,i:number)=><div className="sourceBlock" key={i}>{b.page_no&&<small>{parsed.parser==="pptx"?"Слайд":"Страница"} {b.page_no}</small>}{b.title&&<h4>{b.title}</h4>}{b.kind==="table"||b.kind==="sheet"?documentTable(b.rows||[]):<p>{b.text}</p>}</div>):<div className="empty">Предпросмотр появится после разбора документа. Исходный файл можно скачать по ссылке выше.</div>}
            </div>}
        </article>
        <article><h3>Распознанный текст</h3><div className="parsed">
          {parsed?.warnings?.map((w:string)=><div className="warning" key={w}>{w}</div>)}
          {parsed?.blocks?.map((b:ParsedBlock,i:number)=>{
            const fragments=fields.filter(field=>field.status==="source_verified"&&field.source_document_id===selectedDoc&&field.source_location?.split(" ")[0]===b.path&&field.source_fragment).map(field=>field.source_fragment as string);
            return <div data-path={b.path} className={"block "+(highlightPath===b.path||fragments.length?"highlighted":"")} key={i}><small>{(b.page_no?((parsed.parser==="pptx"?"слайд ":"стр. ")+b.page_no+" · "):"")+b.path}{fragments.length>0&&<span className="evidenceTag">Есть в требованиях</span>}</small>{b.title&&<b>{b.title}</b>}<p>{evidenceText(b.text,fragments)}</p>{(b.kind==="table"||b.kind==="sheet")&&documentTable(b.rows||[])}</div>;
          })}
        </div></article>
      </div>}
    </section>}

    {active==="review"&&<section className="panel">
      <div className="sectionHead">
        <div><h2>Карточка требований</h2><p className="muted">Поля проверяются по источнику и подтверждаются пользователем.</p></div>
        <button onClick={()=>setActive("workforce")}>Настроить расчёт →</button>
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
          <details><summary>Источник</summary><p className="sourceReference"><b>{docs.find(doc=>doc.id===f.source_document_id)?.filename||"Документ не указан"}</b><span>{sourceLocationLabel(f.source_location,docs.find(doc=>doc.id===f.source_document_id)?.parser)}</span></p><blockquote>{evidenceText(fullEvidenceQuote(f.source_document_id?sourceParsed[f.source_document_id]:undefined,f.source_location,f.source_fragment),f.source_fragment?[f.source_fragment]:[])}</blockquote>{f.source_document_id&&<button onClick={()=>openDoc(f.source_document_id as number,(f.source_location||"").split(/\s+page\s+/i)[0])}>Открыть источник в сверке →</button>}</details>
        </div>)}
      </div>
    </section>}

    {active==="workforce"&&<section className="panel">
      <div>
        <h2>Параметры расчёта</h2>
        {form&&[
          ...(areaComponents.length?[]:[["area_m2","Площадь, м²"],["productivity_m2_per_shift","Выработка, м²/смену"]]),
          ["monthly_hours_per_fte","Фонд времени, ч/мес"],["hourly_staff_cost",`Стоимость часа, ${appSettings?.currency_unit_symbol??""}`],
          ["replacement_coefficient","Коэффициент замещения"]
        ].map(function(x){const k=x[0] as keyof CalculationForm;return <label className="control" key={k}><span>{x[1]}</span><input type="number" step="any" value={form[k]} onChange={e=>updateCalculationValue(k,Number(e.target.value))}/></label>})}
        {areaComponents.length>0&&<div className="areaComponents">
          <div className="sectionHead"><div><h3>Площади по адресам и видам работ</h3><p className="muted">Адреса и вид уборки извлечены из ТЗ. Выработка подставляется из внутреннего справочника, если найдена подходящая ставка.</p></div></div>
          <div className="areaTotal"><span>Суммарная площадь без строк «Итого»</span><b>{appSettings?fmt(areaComponents.reduce((sum,item)=>sum+item.area_m2,0),appSettings.display_locale,appSettings.display_number_max_fraction_digits):areaComponents.reduce((sum,item)=>sum+item.area_m2,0)} м²</b></div>
          <details className="areaSource"><summary>Как выбирается выработка</summary><p>Она зависит от вида уборки и механизации, состава операций и их периодичности, типа помещений, загруженности мебелью, планировки и переходов между объектами. Единой ставки для всех работ нет.</p><p>800 м²/смену — имеющаяся демонстрационная упрощённая ставка для регулярной уборки помещений. Проверьте её по вашему прайсу или хронометражу; для уборки снега значение нужно задать отдельно.</p></details>
          {areaComponents.map(component=><div className="areaComponent" key={component.id}>
            <div className="areaComponentTitle"><b>{component.address}</b><span>{component.area_type} · {component.work_type}</span></div>
            <div className="areaComponentInputs">
              <label><span>Площадь, м²</span><input type="number" min="0" step="any" value={component.area_m2} onChange={e=>updateAreaComponent(component.id,{area_m2:e.target.value?Number(e.target.value):0})}/></label>
              <div className="productivityField">
                <div className="productivityFieldLabel"><label htmlFor={`productivity-${component.id}`}>Выработка, м²/смену</label><button type="button" className="helpIcon" aria-label={`Пояснить выработку для адреса ${component.address}`} title="Что означает выработка?" onClick={()=>setProductivityHelp(component)}>i</button></div>
                <input id={`productivity-${component.id}`} type="number" min="0" step="any" value={component.productivity_m2_per_shift??""} placeholder="Нет ставки для этого вида работ" onChange={e=>updateAreaComponent(component.id,{productivity_m2_per_shift:e.target.value?Number(e.target.value):null})}/>
              </div>
            </div>
            {component.productivity_reference&&<p className="fieldHint">Предварительная ставка из справочника «{component.productivity_reference.name}»: {component.productivity_reference.value} {component.productivity_reference.unit}. {component.productivity_reference.notes||""} Проверьте её и при необходимости замените.</p>}
            {!(component.productivity_m2_per_shift&&component.productivity_m2_per_shift>0)&&<p className="warning">{component.productivity_reference?"Введите положительную выработку для этой строки.":"В справочнике нет выработки для этого вида работ. Введите значение из вашего прайса или внутренней нормы."}</p>}
            <div className="areaSchedule">
              <div><h4>Режим уборки и смены</h4><p className="muted">Периодичность берётся из ТЗ. Для фиксированного режима смены в месяц рассчитываются автоматически.</p></div>
              <label><span>Режим</span><select value={component.schedule_mode} onChange={e=>updateScheduleMode(component.id,e.target.value as ScheduleMode)}>
                <option value="daily">Каждый рабочий день</option><option value="weekly">Еженедельно</option><option value="monthly">Ежемесячно</option>
                <option value="on_request">По разовым заявкам</option><option value="custom">Другой режим — ввести число смен</option><option value="unspecified">В ТЗ не указан — ввести число смен</option>
              </select></label>
              <label><span>{component.schedule_mode==="on_request"?"Заявок/выездов в месяц":"Смен в месяц"}</span><input type="number" min="0" step="any" value={shiftsForMode(component.schedule_mode,appSettings)??component.shifts_per_month??""} readOnly={shiftsForMode(component.schedule_mode,appSettings)!==null} placeholder="Укажите ожидаемое число" onChange={e=>updateAreaComponent(component.id,{shifts_per_month:e.target.value?Number(e.target.value):null})}/></label>
              <p className="fieldHint">{scheduleCountHint(component.schedule_mode,appSettings)}{(component.schedule_additional_frequencies?.length??0)>0?" Дополнительные еженедельные/ежемесячные операции показаны отдельно; их трудоёмкость здесь не прибавляется как отдельные смены.":""}</p>
              {component.schedule_status==="needs_input"&&<p className="warning">График в ТЗ не найден. Выберите режим уборки; если он не регулярный, укажите ожидаемое число смен.</p>}
              {component.schedule_warnings?.map((warning,index)=><p className="warning" key={index}>{warning}</p>)}
              {component.schedule_mode==="on_request"&&(component.shifts_per_month||0)<=0&&<p className="warning">ТЗ задаёт уборку по заявкам, но количество заявок в месяц не определено. Укажите ожидаемое число выездов.</p>}
              {component.schedule_source_fragment&&<details className="areaSource"><summary>Источник режима в ТЗ: {component.schedule_source_document_name}</summary><p>{sourceLocationLabel(component.schedule_source_location,docs.find(doc=>doc.id===component.schedule_source_document_id)?.parser)}</p><blockquote>{component.schedule_source_fragment}</blockquote></details>}
            </div>
            <details className="areaSource"><summary>Источник: {component.source_document_name}</summary><p>{sourceLocationLabel(component.source_location,docs.find(doc=>doc.id===component.source_document_id)?.parser)}</p><blockquote>{component.source_fragment}</blockquote><button onClick={()=>openDoc(component.source_document_id,component.source_location.split(/\s+page\s+/i)[0])}>Открыть источник в сверке →</button></details>
            {component.work_type_source_fragment&&<details className="areaSource"><summary>Источник вида работ</summary><p>{component.work_type_source_location} · {docs.find(doc=>doc.id===component.work_type_source_document_id)?.filename}</p><blockquote>{component.work_type_source_fragment}</blockquote></details>}
            {component.curation_warnings?.length?<p className="warning">Проверка строки: {component.curation_warnings.join("; ")}</p>:null}
          </div>)}
        </div>}
        <label className="calculationConfirmation"><input type="checkbox" checked={calculationConfirmed} disabled={!calculationInputsReady} onChange={e=>setCalculationConfirmed(e.target.checked)}/><span><b>Подтверждаю расчёт целиком</b><small>Проверены площади и источники, режимы уборки, ставки выработки и параметры трудоёмкости. При их изменении подтверждение сбросится. Финансовые параметры можно менять и пересчитывать на вкладке «Экономика».</small></span></label>
        <button className="primary" disabled={!criticalReady} onClick={calculate}>Рассчитать трудоёмкость и экономику</button>
        {!form&&<p className="empty">Загрузка настроек расчёта…</p>}
        {!calculationInputsReady&&<p className="warning">{areaComponents.length?"Заполните отсутствующую выработку или задайте режим и количество смен для всех строк.":"Расчёт заблокирован: подтвердите площадь в карточке требований."}</p>}
        {calculationInputsReady&&!calculationConfirmed&&<p className="muted">После проверки всех строк поставьте единое подтверждение, чтобы запустить расчёт.</p>}
      </div>
    </section>}

    {active==="economics"&&<section className="panel">
      <div className="sectionHead"><div><h2>Экономика контракта</h2><p className="muted">Все показатели считает детерминированный Python-модуль.</p></div><button onClick={()=>setActive("decision")}>К решению →</button></div>
      {calc?.components?.length&&appSettings&&<div className="areaResults">
        <h3>Трудоёмкость по адресам и видам уборки</h3>
        <p className="muted">Расчёт использует подтверждённую для каждой строки площадь, выработку и число смен. Экономика ниже считается по общей площади сделки.</p>
        <div className="areaResultsTable"><table><thead><tr><th>Адрес и вид работ</th><th>Площадь</th><th>Выработка</th><th>Режим и источник</th><th>Смен/мес.</th><th>Часов/мес.</th><th>FTE</th><th>Сотрудников</th></tr></thead><tbody>
          {calc.components.map(component=><tr key={component.id}><td><b>{component.address}</b><small>{component.area_type} · {component.work_type}</small><details><summary>{component.source_document_name} · {sourceLocationLabel(component.source_location,docs.find(doc=>doc.id===component.source_document_id)?.parser)}</summary><blockquote>{component.source_fragment}</blockquote><button onClick={()=>openDoc(component.source_document_id,component.source_location.split(/\s+page\s+/i)[0])}>Открыть источник в сверке →</button></details></td><td>{fmt(component.area_m2,appSettings.display_locale,appSettings.display_number_max_fraction_digits)} м²</td><td>{component.productivity_m2_per_shift} м²/смену<small>{component.productivity_reference?.name||"Введено вручную"}</small></td><td><b>{component.schedule_label}</b><small>{component.schedule_mode==="on_request"?"Оценка заявок/мес.":"Смен/мес."}</small><details><summary>{component.schedule_source_document_name||"Режим уборки"} · {sourceLocationLabel(component.schedule_source_location,docs.find(doc=>doc.id===component.schedule_source_document_id)?.parser)}</summary><blockquote>{component.schedule_source_fragment||"Режим задан вручную"}</blockquote></details></td><td>{fmt(component.shifts_per_month||0,appSettings.display_locale,appSettings.display_number_max_fraction_digits)}</td><td>{fmt(component.labor_hours_month||0,appSettings.display_locale,appSettings.display_number_max_fraction_digits)}</td><td>{fmt(component.fte||0,appSettings.display_locale,appSettings.display_number_max_fraction_digits)}</td><td>{component.physical_staff}</td></tr>)}
        </tbody></table></div>
        <p className="areaResultsTotal">По площадкам: {fmt(calc.total_area_m2||0,appSettings.display_locale,appSettings.display_number_max_fraction_digits)} м² · {fmt(calc.labor_hours_month,appSettings.display_locale,appSettings.display_number_max_fraction_digits)} чел.-часов/мес. · {calc.physical_staff_by_site} сотрудников</p>
      </div>}
      <div className="economicsGrid">
        <div className="controls">
          {[
            ["service_price_per_m2_month",`Тариф, ${appSettings?.currency_unit_symbol??""}/м²/мес`],["materials_per_m2_month",`Материалы, ${appSettings?.currency_unit_symbol??""}/м²/мес`],
            ["equipment_per_m2_month",`Техника, ${appSettings?.currency_unit_symbol??""}/м²/мес`],["manager_monthly_cost",`Управление, ${appSettings?.currency_unit_symbol??""}/мес`],
            ["logistics_monthly",`Логистика, ${appSettings?.currency_unit_symbol??""}/мес`],["target_margin","Целевая маржа, %"]
          ].map(function(x){
            const k=x[0] as keyof CalculationForm;
            if(!form)return null;
            const percentageFactor=appSettings?.display_percentage_factor??100;
            const displayValue=k==="target_margin"?form[k]*percentageFactor:form[k];
            return <label className="control" key={k}><span>{x[1]}</span><input type="number" step="any" value={displayValue} onChange={e=>{
              const value=Number(e.target.value);
              updateCalculationValue(k,k==="target_margin"?value/percentageFactor:value,true);
            }}/></label>;
          })}
          <button disabled={busy} onClick={calculate}>Пересчитать</button>
          {calculationDirty&&calc&&<p className="warning">Параметры изменены. Показан предыдущий результат — нажмите «Пересчитать».</p>}
        </div>
        {calc?<div className="kpis">
          <div><span>Выручка без НДС</span><b>{appSettings?money(calc.revenue_net,appSettings.display_locale,appSettings.currency_code,appSettings.display_currency_max_fraction_digits):calc.revenue_net}</b></div>
          <div><span>Полная себестоимость</span><b>{appSettings?money(calc.full_cost,appSettings.display_locale,appSettings.currency_code,appSettings.display_currency_max_fraction_digits):calc.full_cost}</b></div>
          <div><span>Прибыль</span><b>{appSettings?money(calc.profit,appSettings.display_locale,appSettings.currency_code,appSettings.display_currency_max_fraction_digits):calc.profit}</b></div>
          <div><span>Маржа</span><b className={appSettings&&calc.margin<appSettings.no_bid_margin_threshold?"badText":calc.margin<(form?.target_margin??calc.margin)?"warnText":"goodText"}>{appSettings?((calc.margin*appSettings.display_percentage_factor).toFixed(appSettings.display_percentage_decimal_places)+"%"):calc.margin}</b></div>
          <div><span>Break-even</span><b>{appSettings?fmt(calc.break_even_price_per_m2,appSettings.display_locale,appSettings.display_number_max_fraction_digits)+" "+appSettings.currency_unit_symbol+"/м²":calc.break_even_price_per_m2}</b></div>
          <div><span>Тариф для цели</span><b>{appSettings?fmt(calc.target_price_per_m2,appSettings.display_locale,appSettings.display_number_max_fraction_digits)+" "+appSettings.currency_unit_symbol+"/м²":calc.target_price_per_m2}</b></div>
        </div>:<div className="empty">Сначала настройте и подтвердите исходные данные на вкладке «Трудоёмкость».</div>}
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
      </div>
      {productivityHelp&&<div className="modalBackdrop" role="presentation" onMouseDown={event=>{if(event.target===event.currentTarget)setProductivityHelp(null)}}>
        <section className="productivityModal" role="dialog" aria-modal="true" aria-labelledby="productivity-modal-title" tabIndex={-1} onKeyDown={event=>{if(event.key==="Escape")setProductivityHelp(null)}}>
          <button type="button" className="modalClose" aria-label="Закрыть пояснение" autoFocus onClick={()=>setProductivityHelp(null)}>×</button>
          <p className="modalEyebrow">ПОКАЗАТЕЛЬ В РАСЧЁТЕ</p>
          <h2 id="productivity-modal-title">Что означает выработка</h2>
          <p><b>Выработка</b> — площадь, которую один сотрудник успевает убрать за одну смену. Для этой строки: <b>{productivityHelp.address}</b> · {productivityHelp.area_type} · {productivityHelp.work_type}.</p>
          <div className="productivityFormula">Площадь ÷ выработка × часов в смене × смен/выездов в месяц = трудозатраты за месяц</div>
          {productivityHelpNumbers&&appSettings&&<div className="productivityCalculation">
            <h3>Пример для этой строки</h3>
            <p>{fmt(productivityHelp.area_m2,appSettings.display_locale,appSettings.display_number_max_fraction_digits)} м² ÷ {fmt(productivityHelpNumbers.rate,appSettings.display_locale,appSettings.display_number_max_fraction_digits)} м²/смену = <b>{fmt(productivityHelpNumbers.employeeShiftsPerVisit,appSettings.display_locale,2)} смен одного сотрудника на одну уборку</b>.</p>
            <p>Это примерно <b>{fmt(productivityHelpNumbers.hoursPerVisit,appSettings.display_locale,1)} человеко-часов за одну уборку</b> при {fmt(appSettings.hours_per_shift,appSettings.display_locale,1)} часах в смене.</p>
            {productivityHelpNumbers.hoursPerMonth!==null&&<p>При режиме «{productivityHelp.schedule_label}» ({fmt(productivityHelpNumbers.monthlyVisits??0,appSettings.display_locale,1)} смен/выездов в месяц) получится около <b>{fmt(productivityHelpNumbers.hoursPerMonth,appSettings.display_locale,1)} человеко-часов в месяц</b> или {fmt(productivityHelpNumbers.fte??0,appSettings.display_locale,2)} FTE до коэффициента замещения.</p>}
            {productivityHelpNumbers.hoursPerMonth===null&&<p className="warning">Месячный итог появится после ввода ожидаемого числа выездов или смен.</p>}
          </div>}
          {!productivityHelpNumbers&&<p className="warning">Чтобы показать расчёт для этой строки, введите положительную выработку в поле.</p>}
          <p className="muted">Чем больше выработка, тем меньше расчётные трудозатраты и потребность в сотрудниках; чем меньше — тем больше. Ставка зависит от вида работ, механизации, состава операций и условий объекта.</p>
          {productivityHelp.productivity_reference&&<p className="modalNote">Источник ставки: «{productivityHelp.productivity_reference.name}». {productivityHelp.productivity_reference.notes||""} Проверьте демо-значение по прайсу или внутренней норме.</p>}
          {!productivityHelp.productivity_reference&&<p className="modalNote">Ставка введена вручную. Используйте значение из прайса, внутренней нормы или хронометража.</p>}
          <button type="button" className="primary modalAction" onClick={()=>setProductivityHelp(null)}>Понятно</button>
        </section>
      </div>}
    </main>
  </div>
}
