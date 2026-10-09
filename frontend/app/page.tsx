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
type OrganizationSource={value:string;document_id:number;document_name:string;source_location:string;source_fragment:string};
type OrganizationProfile=Record<string,OrganizationSource>;
type ProcessProgress={value:number;label:string};
type ScheduleMode="daily"|"weekly"|"monthly"|"on_request"|"custom"|"unspecified";
type AreaComponent={id:string;origin?:"document"|"manual";manual_line_id?:number;price_list_item_id?:number|null;company_service_name?:string|null;price_per_m2_month?:number|null;address:string;area_type:string;work_type:string;work_type_source_document_id:number|null;work_type_source_location:string;work_type_source_fragment:string;area_m2:number;source_document_id:number|null;source_document_name:string;source_location:string;source_fragment:string;schedule_mode:ScheduleMode;schedule_label:string;schedule_status:string;schedule_warnings:string[];schedule_source_document_id:number|null;schedule_source_document_name:string|null;schedule_source_location:string;schedule_source_fragment:string;schedule_additional_frequencies?:string[];curation_status?:string;curation_warnings?:string[];productivity_m2_per_shift:number|null;productivity_reference?:{id:number;name:string;unit:string;value:number;notes:string|null}|null;shifts_per_month:number|null;monthly_price?:number;contract_price?:number;labor_hours_month?:number;fte?:number;physical_staff?:number};
type FormulaSetting={key:string;label:string;description:string;expression:string;default_expression:string;variables:string[]};
type PriceListItem={id:number;name:string;area_type:string;work_type:string;price_per_m2_month:number;productivity_m2_per_shift:number|null;notes:string|null;is_active:boolean};
type DemoProviderTariff={id:string;provider:string;city:string;object_type:string;service:string;area_range:string|null;price_min:number|null;price_max:number|null;price_unit:string;source_url:string;source_date:string;source_dataset:string;evidence:string;details:string|null};
type DemoProviderTariffs={notice:string;featured_ids:string[];items:DemoProviderTariff[]};
type PriceListDraft={name:string;area_type:string;work_type:string;price_per_m2_month:string;productivity_m2_per_shift:string;notes:string};
type ManualServiceDraft={address:string;area_type:string;work_type:string;area_m2:string;price_list_item_id:string;price_per_m2_month:string;productivity_m2_per_shift:string};
type Calc={calculation_id:number;area_m2?:number;labor_hours_month:number;fte:number;physical_staff:number;physical_staff_by_site?:number;total_area_m2?:number;components?:AreaComponent[];revenue_with_vat:number;revenue_net:number;direct_cost:number;full_cost:number;profit:number;margin:number;break_even_price_per_m2:number;target_price_per_m2:number;decision:string;conditions:string[];sensitivity:{delta:number;price:number;margin:number}[]};
type CalculationForm={area_m2:number;service_price_per_m2_month:number;productivity_m2_per_shift:number;monthly_hours_per_fte:number;hourly_staff_cost:number;replacement_coefficient:number;manager_monthly_cost:number;materials_per_m2_month:number;equipment_per_m2_month:number;logistics_monthly:number;overhead_rate:number;contingency_rate:number;target_margin:number;vat_rate:number;contract_months:number};
type SavedCalculation={id:number;is_current:boolean;input:{confirmed?:boolean;assumptions?:CalculationForm;components?:Partial<AreaComponent>[]}&Partial<CalculationForm>;output:Calc&{aggregate?:Calc}};
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
  const [sidebarCollapsed,setSidebarCollapsed]=useState(false);
  const [documentsCollapsed,setDocumentsCollapsed]=useState(false);
  const [sensitivityHelp,setSensitivityHelp]=useState(false);
  const [proposalForm,setProposalForm]=useState({customer_name:"",customer_address:"",customer_inn:"",customer_kpp:"",customer_ogrn:"",customer_contact_person:"",customer_phone:"",customer_email:"",supplier_name:"",contact_details:"",validity_days:10,additional_terms:""});
  const [organizationProfile,setOrganizationProfile]=useState<OrganizationProfile>({});
  const [proposalTouched,setProposalTouched]=useState<Set<string>>(new Set());
  const [formulaSettings,setFormulaSettings]=useState<FormulaSetting[]>([]);
  const [formulaBusy,setFormulaBusy]=useState(false);
  const [priceListItems,setPriceListItems]=useState<PriceListItem[]>([]);
  const [priceListView,setPriceListView]=useState<"catalog"|"demo"|"formulas">("catalog");
  const [priceListSavedId,setPriceListSavedId]=useState<number|null>(null);
  const [demoProviderTariffs,setDemoProviderTariffs]=useState<DemoProviderTariffs|null>(null);
  const [demoTariffQuery,setDemoTariffQuery]=useState("");
  const [priceListDraft,setPriceListDraft]=useState<PriceListDraft>({name:"",area_type:"Площадь объекта",work_type:"",price_per_m2_month:"",productivity_m2_per_shift:"",notes:""});
  const [priceListBusy,setPriceListBusy]=useState(false);
  const [manualServiceDraft,setManualServiceDraft]=useState<ManualServiceDraft>({address:"",area_type:"Площадь объекта",work_type:"",area_m2:"",price_list_item_id:"",price_per_m2_month:"",productivity_m2_per_shift:""});
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
  async function refresh(restoreCalculation=false){
    if(!deal)return;
    const all=await Promise.all([
      req("/deals/"+deal.id+"/documents"),
      req("/deals/"+deal.id+"/fields"),
      req("/deals/"+deal.id+"/pipeline"),
      req("/deals/"+deal.id+"/area-components"),
      req("/deals/"+deal.id+"/calculations"),
      req("/deals/"+deal.id+"/organization-profile")
    ]);
    setDocs(all[0]);setFields(all[1]);setRuns(all[2]);
    const latestCalculation:SavedCalculation|undefined=all[4]?.[0];
    if(latestCalculation){
      const output=latestCalculation.output;
      setCalc(output?.aggregate?{...output.aggregate,calculation_id:latestCalculation.id,components:output.components,total_area_m2:output.total_area_m2,physical_staff_by_site:output.physical_staff_by_site}:{...output,calculation_id:latestCalculation.id});
      setCalculationDirty(current=>current||!latestCalculation.is_current);
      if(restoreCalculation){
        setCalculationConfirmed(Boolean(latestCalculation.is_current&&latestCalculation.input?.confirmed));
        if(latestCalculation.is_current){
          const assumptions=latestCalculation.input.assumptions??latestCalculation.input;
          setForm(current=>current?{...current,...assumptions}:current);
        }
      }
    }else{setCalc(null);setCalculationDirty(false);setCalculationConfirmed(false)}
    setAreaComponents((current:AreaComponent[])=>all[3].map((source:AreaComponent)=>{
      const previous=current.find(item=>item.id===source.id);
      const saved=restoreCalculation&&latestCalculation?.is_current?latestCalculation.input.components?.find(item=>item.id===source.id):undefined;
      return {...source,area_m2:previous?.area_m2??saved?.area_m2??source.area_m2,
        productivity_m2_per_shift:previous?.productivity_m2_per_shift??saved?.productivity_m2_per_shift??source.productivity_m2_per_shift,
        schedule_mode:previous?.schedule_mode??saved?.schedule_mode??source.schedule_mode,
        shifts_per_month:previous?.shifts_per_month??saved?.shifts_per_month??source.shifts_per_month};
    }));
    setOrganizationProfile(all[5]||{});
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
  useEffect(()=>{req("/formulas").then(setFormulaSettings).catch((e:any)=>setError(e.message))},[]);
  useEffect(()=>{req("/price-list").then(setPriceListItems).catch((e:any)=>setError(e.message))},[]);
  useEffect(()=>{req("/demo-provider-tariffs").then(setDemoProviderTariffs).catch((e:any)=>setError(e.message))},[]);
  useEffect(()=>{if(deal)refresh(true).catch(()=>{})},[deal?.id]);
  useEffect(()=>{
    const profileFields=["customer_name","customer_address","customer_inn","customer_kpp","customer_ogrn","customer_contact_person","customer_phone","customer_email"] as const;
    setProposalForm(current=>{
      const next={...current};
      profileFields.forEach(key=>{
        if(!proposalTouched.has(key)&&!next[key]&&organizationProfile[key]?.value)next[key]=organizationProfile[key].value;
      });
      return next;
    });
  },[organizationProfile,proposalTouched]);
  useEffect(()=>{
    if(!productivityHelp&&!sensitivityHelp)return;
    const previousOverflow=document.body.style.overflow;
    document.body.style.overflow="hidden";
    return()=>{document.body.style.overflow=previousOverflow};
  },[productivityHelp,sensitivityHelp]);
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
      const d=await req("/deals?title="+encodeURIComponent("Новая сделка"),{method:"POST"});
      window.localStorage.setItem("dealCopilot.activeDealId",String(d.id));
      setOrganizationProfile({});setProposalTouched(new Set());
      setProposalForm(current=>({...current,customer_name:"",customer_address:"",customer_inn:"",customer_kpp:"",customer_ogrn:"",customer_contact_person:"",customer_phone:"",customer_email:""}));
      setDeal(d);setDocs([]);setFields([]);setRuns([]);setAreaComponents([]);setSourceParsed({});setForm(appSettings?.calculation_defaults??null);setCalc(null);setCalculationDirty(false);setCalculationConfirmed(false);setActive("upload");
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
    setCalculationConfirmed(false);setCalculationDirty(true);
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
  function sourceArrow(id:number|undefined|null,location:string|undefined|null,label:string,title?:string){
    if(!id)return null;
    const path=location?.split(/\s+page\s+/i)[0];
    return <button type="button" className="sourceJump" aria-label={label} title={title||label} onClick={()=>{void openDoc(id,path)}}>
      <svg aria-hidden="true" viewBox="0 0 20 20" fill="none"><path d="M3.5 10h12m-5-5 5 5-5 5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>
    </button>;
  }
  function updateProposalField(key:string,value:string|number){
    setProposalTouched(current=>new Set(current).add(key));
    setProposalForm(current=>({...current,[key]:value}));
  }
  function organizationSource(key:string,label:string){
    const source=organizationProfile[key];
    return sourceArrow(source?.document_id,source?.source_location,`Открыть источник: ${label}`,source?`${source.document_name} · ${source.source_fragment}`:label);
  }
  async function saveField(row:Field,value:string){
    await req("/fields/"+row.id,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({value:value,confirmed:true})});
    if(row.key==="area_m2"){
      const numeric=Number(String(value).replace(",",".").replace(/[^0-9.\-]/g,""));
      if(Number.isFinite(numeric) && numeric>0) setForm(current=>current?({...current,area_m2:numeric}):current);
    }
    if(row.key==="contract_months"){
      const months=Number(String(value).replace(",","."));
      if(Number.isInteger(months)&&months>0)setForm(current=>current?({...current,contract_months:months}):current);
    }
    setCalculationConfirmed(false);setCalculationDirty(true);
    await refresh();
  }
  async function calculate(){
    if(!deal||!form)return;
    if(!calculationInputsReady){setError(areaComponents.length?"Заполните выработку и режим уборки для каждой строки. Если график задан заявками, укажите ожидаемые выезды в месяц.":"Подтвердите критическое поле «Площадь» перед расчётом.");setActive(areaComponents.length?"workforce":"review");return;}
    if(!calculationConfirmed){setError("Подтвердите расчёт целиком на вкладке «Трудоёмкость».");setActive("workforce");return;}
    setBusy(true);setError("");
    try{
      const path=areaComponents.length?"/calculate-breakdown":"/calculate";
      const body=areaComponents.length?{confirmed:calculationConfirmed,assumptions:form,components:areaComponents.map(({id,origin,price_list_item_id,area_m2,productivity_m2_per_shift,schedule_mode,shifts_per_month,price_per_m2_month})=>({id,area_m2,productivity_m2_per_shift,schedule_mode,shifts_per_month,...(origin!=="manual"&&price_list_item_id?{}:{price_per_m2_month})}))}:form;
      const result=await req("/deals/"+deal.id+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
      setCalc(result);setCalculationDirty(false);setActive("economics");await refresh(true);
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }

  async function downloadProposal(){
    if(!deal||!calc||calculationDirty||!calculationConfirmed){setError("Подтвердите исходные данные и пересчитайте сделку перед скачиванием КП.");return;}
    setBusy(true);setError("");
    try{
      const response=await fetch(API+"/deals/"+deal.id+"/proposal",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(proposalForm)});
      if(!response.ok){const body=await response.json().catch(()=>null);throw new Error(body?.detail||`Ошибка формирования КП (${response.status})`);}
      const blob=await response.blob();
      const url=URL.createObjectURL(blob);const link=document.createElement("a");
      link.href=url;link.download=`commercial-proposal-deal-${deal.id}.docx`;link.click();URL.revokeObjectURL(url);
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }

  function updateAreaComponent(id:string,patch:Partial<AreaComponent>){
    setAreaComponents(current=>current.map(component=>component.id===id?({...component,...patch}):component));
    setCalculationConfirmed(false);
    setCalculationDirty(true);
  }

  function updateScheduleMode(id:string,mode:ScheduleMode){
    const patch={schedule_mode:mode,shifts_per_month:shiftsForMode(mode,appSettings)};
    updateAreaComponent(id,patch);
    const component=areaComponents.find(item=>item.id===id);
    if(component?.origin==="manual")void saveManualServiceLine(component,patch);
  }

  function updateCalculationValue(key:keyof CalculationForm,value:number,preserveConfirmation=false){
    setForm(current=>current?({...current,[key]:value}):current);
    setError("");
    if(preserveConfirmation){setCalculationDirty(true);return;}
    setCalculationConfirmed(false);setCalculationDirty(true);
  }

  async function addManualArea(){
    if(!deal)return;
    const numeric=Number(manualArea.replace(",","."));
    if(!Number.isFinite(numeric)||numeric<=0){setError("Введите положительную площадь в м².");return;}
    setBusy(true);setError("");
    try{
      await req("/deals/"+deal.id+"/fields/area",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({value:numeric})});
      setForm(current=>current?({...current,area_m2:numeric}):current);
      setCalculationConfirmed(false);setCalculationDirty(true);
      setManualArea("");await refresh();
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }

  async function addManualServiceLine(){
    if(!deal)return;
    const area=Number(manualServiceDraft.area_m2.replace(",","."));
    if(!manualServiceDraft.address.trim()||!manualServiceDraft.work_type.trim()||!Number.isFinite(area)||area<=0){
      setError("Для ручной услуги укажите адрес, вид работ и положительную площадь.");return;
    }
    setBusy(true);setError("");
    try{
      const price=Number(manualServiceDraft.price_per_m2_month.replace(",","."));
      const productivity=Number(manualServiceDraft.productivity_m2_per_shift.replace(",","."));
      await req(`/deals/${deal.id}/area-components/manual`,{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({...manualServiceDraft,address:manualServiceDraft.address.trim(),work_type:manualServiceDraft.work_type.trim(),area_m2:area,
          price_list_item_id:manualServiceDraft.price_list_item_id?Number(manualServiceDraft.price_list_item_id):null,
          price_per_m2_month:Number.isFinite(price)&&price>0?price:null,
          productivity_m2_per_shift:Number.isFinite(productivity)&&productivity>0?productivity:null})});
      setManualServiceDraft({address:"",area_type:"Площадь объекта",work_type:"",area_m2:"",price_list_item_id:"",price_per_m2_month:"",productivity_m2_per_shift:""});
      setCalculationConfirmed(false);setCalculationDirty(true);await refresh();
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }

  async function saveManualServiceLine(line:AreaComponent,patch:Partial<AreaComponent>){
    if(!deal||!line.manual_line_id)return;
    const payload=Object.fromEntries(Object.entries(patch).filter(([key])=>["address","area_type","work_type","area_m2","schedule_mode","shifts_per_month","productivity_m2_per_shift","price_list_item_id","price_per_m2_month"].includes(key)));
    if(!Object.keys(payload).length)return;
    try{
      await req(`/deals/${deal.id}/area-components/manual/${line.manual_line_id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    }catch(e:any){setError(e.message)}
  }

  async function deleteManualServiceLine(line:AreaComponent){
    if(!deal||!line.manual_line_id)return;
    setBusy(true);setError("");
    try{
      await req(`/deals/${deal.id}/area-components/manual/${line.manual_line_id}`,{method:"DELETE"});
      setCalculationConfirmed(false);setCalculationDirty(true);await refresh();
    }catch(e:any){setError(e.message)}finally{setBusy(false)}
  }

  async function saveCalculationFormulas(){
    setFormulaBusy(true);setError("");
    try{
      const saved=await req("/formulas",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({formulas:formulaSettings.map(({key,expression})=>({key,expression}))})});
      setFormulaSettings(saved);setCalculationDirty(Boolean(calc));
    }catch(e:any){setError(e.message)}finally{setFormulaBusy(false)}
  }

  function selectPriceListItem(id:string){
    const item=priceListItems.find(entry=>entry.id===Number(id));
    setManualServiceDraft(current=>item?({...current,price_list_item_id:id,area_type:item.area_type,work_type:item.work_type,
      price_per_m2_month:String(item.price_per_m2_month),productivity_m2_per_shift:item.productivity_m2_per_shift===null?"":String(item.productivity_m2_per_shift)}):
      ({...current,price_list_item_id:""}));
  }

  async function applyPriceListItemToLine(line:AreaComponent,id:string){
    const item=priceListItems.find(entry=>entry.id===Number(id));
    const patch:Partial<AreaComponent>=line.origin==="manual"
      ?item?{price_list_item_id:item.id,area_type:item.area_type,work_type:item.work_type,
          price_per_m2_month:item.price_per_m2_month,productivity_m2_per_shift:item.productivity_m2_per_shift}:
        {price_list_item_id:null,price_per_m2_month:null}
      :item?{price_list_item_id:item.id,price_per_m2_month:item.price_per_m2_month,
          productivity_m2_per_shift:item.productivity_m2_per_shift??line.productivity_m2_per_shift}:
        {price_list_item_id:null,price_per_m2_month:null};
    updateAreaComponent(line.id,patch);
    if(line.origin==="manual"){
      await saveManualServiceLine(line,patch);
      return;
    }
    if(!deal)return;
    setError("");
    try{
      await req(`/deals/${deal.id}/component-price-selection`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({component_id:line.id,price_list_item_id:item?.id??null})});
    }catch(e:any){setError(e.message);await refresh()}
  }

  async function createPriceListItem(){
    const price=Number(priceListDraft.price_per_m2_month.replace(",","."));
    const productivity=Number(priceListDraft.productivity_m2_per_shift.replace(",","."));
    if(!priceListDraft.name.trim()||!priceListDraft.work_type.trim()||!Number.isFinite(price)||price<=0){
      setError("Укажите название услуги, описание работ и положительный тариф за м² в месяц.");return;
    }
    setPriceListBusy(true);setError("");
    try{
      const item=await req("/price-list",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
        ...priceListDraft,name:priceListDraft.name.trim(),area_type:priceListDraft.area_type.trim()||"Площадь объекта",
        work_type:priceListDraft.work_type.trim(),price_per_m2_month:price,
        productivity_m2_per_shift:Number.isFinite(productivity)&&productivity>0?productivity:null,
        notes:priceListDraft.notes.trim()||null})});
      setPriceListItems(current=>[...current,item]);
      setPriceListDraft({name:"",area_type:"Площадь объекта",work_type:"",price_per_m2_month:"",productivity_m2_per_shift:"",notes:""});
    }catch(e:any){setError(e.message)}finally{setPriceListBusy(false)}
  }

  async function savePriceListItem(id:number,patch:Partial<Omit<PriceListItem,"id">>){
    setError("");
    if(patch.name!==undefined&&!patch.name.trim()){
      setError("Введите название услуги.");return;
    }
    if(patch.price_per_m2_month!==undefined&&(!Number.isFinite(patch.price_per_m2_month)||patch.price_per_m2_month<=0)){
      setError("Тариф должен быть положительным числом.");return;
    }
    setPriceListBusy(true);
    try{
      const normalizedPatch={...patch,...(patch.name!==undefined?{name:patch.name.trim()}: {})};
      const saved=await req(`/price-list/${id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify(normalizedPatch)});
      setPriceListItems(current=>current.map(item=>item.id===id?saved:item));
      if(patch.price_per_m2_month!==undefined)setAreaComponents(current=>current.map(line=>line.origin!=="manual"&&line.price_list_item_id===id?({...line,price_per_m2_month:saved.price_per_m2_month}):line));
      if(patch.name!==undefined)setPriceListSavedId(id);
      if(calc&&["price_per_m2_month","productivity_m2_per_shift","work_type","area_type"].some(key=>key in patch))setCalculationDirty(true);
    }catch(e:any){setError(e.message);const items=await req("/price-list").catch(()=>null);if(items)setPriceListItems(items)}
    finally{setPriceListBusy(false)}
  }

  async function archivePriceListItem(item:PriceListItem){
    setPriceListBusy(true);setError("");
    try{
      const saved=await req(`/price-list/${item.id}`,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({is_active:!item.is_active})});
      setPriceListItems(current=>current.map(entry=>entry.id===item.id?saved:entry));
      if(calc)setCalculationDirty(true);
    }catch(e:any){setError(e.message)}finally{setPriceListBusy(false)}
  }

  const tabs=[
    {key:"upload",label:"Новая сделка",title:"Рабочее пространство",description:"Создайте сделку и загрузите тендерные материалы."},
    {key:"documents",label:"Документы",title:"Документы",description:"Сопоставьте оригинал файла с результатом разбора."},
    {key:"review",label:"Требования",title:"Проверка требований",description:"Проверьте извлечённые значения и подтвердите исходные данные."},
    {key:"workforce",label:"Трудоёмкость",title:"Расчёт трудоёмкости",description:"Настройте параметры объекта и проверьте потребность в персонале."},
    {key:"economics",label:"Экономика",title:"Экономика контракта",description:"Итоги расчёта, себестоимость, маржа и чувствительность к тарифу."},
    {key:"proposal",label:"Коммерческое предложение",title:"Формирование КП",description:"Подготовьте редактируемый проект коммерческого предложения по подтверждённым данным."},
  ];
  const serviceTab={key:"pipeline",label:"Контроль обработки",title:"Контроль обработки",description:"Служебная информация о шагах распознавания и расчёта."};
  const formulaTab={key:"settings",label:"Настройки",title:"Настройки компании",description:"Прайс-лист услуг и формулы расчёта."};
  const currentTab=tabs.find(tab=>tab.key===active)??(active==="pipeline"?serviceTab:active==="settings"?formulaTab:tabs[0]);
  const stageIndex=tabs.findIndex(tab=>tab.key===active);
  const moveStage=(offset:number)=>{const next=tabs[Math.max(0,Math.min(tabs.length-1,stageIndex+offset))];if(next)setActive(next.key)};
  const productivityHelpNumbers=productivityHelp?productivityEstimate(productivityHelp,appSettings,form?.monthly_hours_per_fte??0):null;
  const confirmed=fields.filter(x=>x.confirmed).length;
  const areaField=fields.find(x=>x.key==="area_m2");
  const proposalContractMonths=form?.contract_months||1;
  const areaBreakdownReady=areaComponents.length>0&&areaComponents.every(component=>Boolean(
    component.curation_status==="verified"&&component.schedule_status!=="needs_review"&&component.area_m2>0
    &&(component.productivity_m2_per_shift||0)>0
    &&((shiftsForMode(component.schedule_mode,appSettings)??component.shifts_per_month)||0)>0
  ));
  const calculationInputsReady=Boolean(form&&(areaComponents.length?areaBreakdownReady:areaField?.confirmed&&areaField.value));
  const criticalReady=Boolean(calculationInputsReady&&calculationConfirmed);
  const statusClass=calc?.decision==="BID"?"good":calc?.decision==="NO BID"?"bad":"warn";

  return <div className={"appShell "+(sidebarCollapsed?"sidebarCollapsed":"")}>
    {!sidebarCollapsed&&<aside className="sidebar">
      <div className="sidebarBrand">
        <div className="brandMark" aria-hidden="true">DC</div>
        <div><span className="brand">Deal Copilot</span></div>
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

      <nav className="sideNav serviceNav" aria-label="Служебные разделы">
        <button className={active==="pipeline"?"active":""} aria-current={active==="pipeline"?"page":undefined} onClick={()=>setActive("pipeline")}>
          <span className="navIndex">⚙</span><span><b>Контроль обработки</b><small>Журнал шагов и ошибок</small></span><span className="navArrow" aria-hidden="true">→</span>
        </button>
        <button className={active==="settings"?"active":""} aria-current={active==="settings"?"page":undefined} onClick={()=>setActive("settings")}>
          <span className="navIndex">⚙</span><span><b>Настройки компании</b><small>Прайс-лист и формулы</small></span><span className="navArrow" aria-hidden="true">→</span>
        </button>
      </nav>

      {!appSettings?.demo_mode&&<footer className="sidebarFooter">
        <span className="modeDot live"/>
        <span>{appSettings?.llm_provider==="local"?"MiMo · локально":"MiMo · API"}</span>
      </footer>}
      <button className="sidebarToggle" type="button" onClick={()=>setSidebarCollapsed(true)} aria-label="Скрыть левую панель" title="Скрыть левую панель">‹</button>
    </aside>}

    <main className="workspace">
      <header className="workspaceHeader">
        <div>
          <p className="workspaceEyebrow">DEAL COPILOT <span>/</span> {deal?("СДЕЛКА #"+deal.id):"НОВЫЙ ПРОЕКТ"}</p>
          <h1>{currentTab.title}</h1>
          <p>{currentTab.description}</p>
        </div>
        <div className="workspaceHeaderActions">{sidebarCollapsed&&<button type="button" className="sidebarRestore" onClick={()=>setSidebarCollapsed(false)} aria-label="Показать левую панель" title="Показать левую панель">☰</button>}{active!=="pipeline"&&<div className="workspaceStep"><span>ШАГ</span><b>{String(stageIndex+1).padStart(2,"0")}</b><i>/</i><span>{String(tabs.length).padStart(2,"0")}</span></div>}</div>
      </header>

      {error&&<div className="error" role="alert">{error}</div>}

      <div className="workspaceContent">
    {active==="upload"&&<section className="panel two">
      <div>
        <h2><span className="panelStep">01</span>Создать сделку</h2>
        <p className="muted">Создайте сделку, чтобы связать документы, требования, расчёт и коммерческое предложение.</p>
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
        <div className="sectionActions"><button type="button" onClick={()=>setDocumentsCollapsed(value=>!value)} aria-expanded={!documentsCollapsed}>{documentsCollapsed?"Показать детали":"Свернуть детали"}</button>
        <button disabled={!docs.length||busy} onClick={process}>Распознать и извлечь требования</button>
        </div>
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
      {selectedDoc&&!documentsCollapsed&&<div className="split">
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
            {sourceArrow(f.source_document_id,f.source_location,`Открыть источник для поля «${f.label}»`,docs.find(doc=>doc.id===f.source_document_id)?.filename)}
            <button className={f.confirmed?"confirmed":""} onClick={()=>saveField(f,f.value||"")}>{f.confirmed?"✓ Подтверждено":"Подтвердить"}</button>
          </div>
          <details><summary>Цитата в документе</summary><p className="sourceReference"><b>{f.source_document_id?<button type="button" className="sourceFileLink" onClick={()=>void openDoc(f.source_document_id!,f.source_location||undefined)}>{docs.find(doc=>doc.id===f.source_document_id)?.filename||"Открыть документ"}</button>:"Документ не указан"}</b><span>{sourceLocationLabel(f.source_location,docs.find(doc=>doc.id===f.source_document_id)?.parser)}</span></p><blockquote>{evidenceText(fullEvidenceQuote(f.source_document_id?sourceParsed[f.source_document_id]:undefined,f.source_location,f.source_fragment),f.source_fragment?[f.source_fragment]:[])}</blockquote></details>
        </div>)}
      </div>
      <div className="manualServices">
        <div><h3>Требуемые услуги</h3><p className="muted">Выберите услугу из прайс-листа компании: её вид работ, тариф и норматив подставятся в строку. Площадь и адрес заполните для этой сделки. Цена и норматив останутся редактируемыми.</p></div>
        {areaComponents.map(component=><div className="manualServiceRow" key={component.id}>
          <div className="manualServiceRowHead"><b>{component.origin==="manual"?"Ручная строка":"Из документа"}</b>{component.origin!=="manual"&&sourceArrow(component.source_document_id,component.source_location,`Открыть источник строки ${component.address}`,component.source_document_name)}</div>
          {component.origin==="manual"?<div className="manualServiceFields">
            <label>Позиция прайс-листа<select value={component.price_list_item_id??""} onChange={e=>applyPriceListItemToLine(component,e.target.value)}><option value="">Своя услуга</option>{priceListItems.filter(item=>item.is_active||item.id===component.price_list_item_id).map(item=><option key={item.id} value={item.id}>{item.name}{item.is_active?"":" · архив"}</option>)}</select></label>
            <label>Адрес<input value={component.address} onChange={e=>updateAreaComponent(component.id,{address:e.target.value})} onBlur={e=>void saveManualServiceLine(component,{address:e.target.value})}/></label>
            <label>Вид площади<input value={component.area_type} onChange={e=>updateAreaComponent(component.id,{area_type:e.target.value})} onBlur={e=>void saveManualServiceLine(component,{area_type:e.target.value})}/></label>
            <label>Вид работ<input value={component.work_type} onChange={e=>updateAreaComponent(component.id,{work_type:e.target.value})} onBlur={e=>void saveManualServiceLine(component,{work_type:e.target.value})}/></label>
            <label>Площадь, м²<input type="number" min="0" step="any" value={component.area_m2} onChange={e=>updateAreaComponent(component.id,{area_m2:e.target.value?Number(e.target.value):0})} onBlur={e=>void saveManualServiceLine(component,{area_m2:Number(e.target.value)})}/></label>
            <label>Тариф, {appSettings?.currency_unit_symbol??"₽"}/м²/мес<input type="number" min="0" step="any" value={component.price_per_m2_month??""} placeholder={String(form?.service_price_per_m2_month??"")} onChange={e=>updateAreaComponent(component.id,{price_per_m2_month:e.target.value?Number(e.target.value):null})} onBlur={e=>void saveManualServiceLine(component,{price_per_m2_month:e.target.value?Number(e.target.value):null})}/></label>
            <button type="button" className="dangerButton" disabled={busy} onClick={()=>void deleteManualServiceLine(component)}>Удалить строку</button>
          </div>:<div className="documentServiceFields">
            <p>{component.address} · {component.area_type} · {component.work_type} · {fmt(component.area_m2,appSettings?.display_locale||"ru-RU",appSettings?.display_number_max_fraction_digits||1)} м²</p>
            <label>Услуга и тариф для расчёта КП<select value={component.price_list_item_id??""} onChange={e=>void applyPriceListItemToLine(component,e.target.value)}><option value="">Без позиции прайс-листа</option>{priceListItems.filter(item=>item.is_active||item.id===component.price_list_item_id).map(item=><option key={item.id} value={item.id}>{item.name} · {fmt(item.price_per_m2_month,appSettings?.display_locale||"ru-RU",appSettings?.display_currency_max_fraction_digits||2)} {appSettings?.currency_unit_symbol??"₽"}/м²/мес</option>)}</select></label>
          </div>}
        </div>)}
        <div className="manualServiceForm">
          <label>Услуга из прайс-листа<select value={manualServiceDraft.price_list_item_id} onChange={e=>selectPriceListItem(e.target.value)}><option value="">Выберите услугу или заполните вручную</option>{priceListItems.filter(item=>item.is_active).map(item=><option key={item.id} value={item.id}>{item.name} · {fmt(item.price_per_m2_month,appSettings?.display_locale||"ru-RU",appSettings?.display_currency_max_fraction_digits||2)} {appSettings?.currency_unit_symbol??"₽"}/м²/мес</option>)}</select></label>
          <label>Адрес<input value={manualServiceDraft.address} onChange={e=>setManualServiceDraft({...manualServiceDraft,address:e.target.value})} placeholder="Адрес или название объекта"/></label>
          <label>Вид площади<input value={manualServiceDraft.area_type} onChange={e=>setManualServiceDraft({...manualServiceDraft,area_type:e.target.value})} placeholder="Помещения, территория…"/></label>
          <label>Требуемая услуга<input value={manualServiceDraft.work_type} onChange={e=>setManualServiceDraft({...manualServiceDraft,work_type:e.target.value})} placeholder="Например, уборка снега"/></label>
          <label>Площадь, м²<input type="number" min="0" step="any" value={manualServiceDraft.area_m2} onChange={e=>setManualServiceDraft({...manualServiceDraft,area_m2:e.target.value})}/></label>
          <label>Тариф, {appSettings?.currency_unit_symbol??"₽"}/м²/мес<input type="number" min="0" step="any" value={manualServiceDraft.price_per_m2_month} onChange={e=>setManualServiceDraft({...manualServiceDraft,price_per_m2_month:e.target.value})} placeholder={String(form?.service_price_per_m2_month??"")}/></label>
          <label>Выработка, м²/смену<input type="number" min="0" step="any" value={manualServiceDraft.productivity_m2_per_shift} onChange={e=>setManualServiceDraft({...manualServiceDraft,productivity_m2_per_shift:e.target.value})} placeholder="Можно задать позже"/></label>
          <button type="button" disabled={busy} onClick={()=>void addManualServiceLine()}>Добавить услугу в расчёт</button>
        </div>
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
          <div className="sectionHead"><div><h3>Услуги по адресам и видам работ</h3><p className="muted">В расчёт вошли строки из ТЗ и ручные услуги. Выработка подставляется из справочника, если найдена подходящая ставка.</p></div></div>
          <div className="areaTotal"><span>Суммарная площадь услуг</span><b>{appSettings?fmt(areaComponents.reduce((sum,item)=>sum+item.area_m2,0),appSettings.display_locale,appSettings.display_number_max_fraction_digits):areaComponents.reduce((sum,item)=>sum+item.area_m2,0)} м²</b></div>
          {areaComponents.map(component=><div className="areaComponent" key={component.id}>
            <div className="areaComponentTitle"><b>{component.address}</b><span className="workTypeValue"><strong>{component.work_type}</strong>{sourceArrow(component.work_type_source_document_id,component.work_type_source_location,`Открыть источник вида работ для адреса ${component.address}`,docs.find(doc=>doc.id===component.work_type_source_document_id)?.filename)}</span><small>{component.area_type}</small></div>
            <div className="areaLineInputs">
              <label><span className="areaMeasureLabel">Площадь, м²{component.origin!=="manual"&&sourceArrow(component.source_document_id,component.source_location,`Открыть источник площади для адреса ${component.address}`,component.source_document_name)}</span><input type="number" min="0" step="any" value={component.area_m2} onChange={e=>updateAreaComponent(component.id,{area_m2:e.target.value?Number(e.target.value):0})} onBlur={e=>component.origin==="manual"&&void saveManualServiceLine(component,{area_m2:Number(e.target.value)})}/></label>
              <div className="productivityField">
                <div className="productivityFieldLabel"><label htmlFor={`productivity-${component.id}`}>Выработка, м²/смену</label><button type="button" className="helpIcon" aria-label={`Пояснить выработку для адреса ${component.address}`} title="Что означает выработка?" onClick={()=>setProductivityHelp(component)}>i</button></div>
                <input id={`productivity-${component.id}`} type="number" min="0" step="any" value={component.productivity_m2_per_shift??""} placeholder="Нет ставки для этого вида работ" onChange={e=>updateAreaComponent(component.id,{productivity_m2_per_shift:e.target.value?Number(e.target.value):null})} onBlur={e=>component.origin==="manual"&&void saveManualServiceLine(component,{productivity_m2_per_shift:e.target.value?Number(e.target.value):null})}/>
              </div>
              <label><span>Режим{sourceArrow(component.schedule_source_document_id,component.schedule_source_location,`Открыть источник режима для адреса ${component.address}`,component.schedule_source_document_name||"Источник режима")}</span><select value={component.schedule_mode} onChange={e=>updateScheduleMode(component.id,e.target.value as ScheduleMode)}>
                <option value="daily">Каждый рабочий день</option><option value="weekly">Еженедельно</option><option value="monthly">Ежемесячно</option>
                <option value="on_request">По разовым заявкам</option><option value="custom">Другой режим — ввести число смен</option><option value="unspecified">В ТЗ не указан — ввести число смен</option>
              </select></label>
              <label><span>{component.schedule_mode==="on_request"?"Заявок/выездов в месяц":"Смен в месяц"}</span><input type="number" min="0" step="any" value={shiftsForMode(component.schedule_mode,appSettings)??component.shifts_per_month??""} readOnly={shiftsForMode(component.schedule_mode,appSettings)!==null} placeholder="Укажите ожидаемое число" onChange={e=>updateAreaComponent(component.id,{shifts_per_month:e.target.value?Number(e.target.value):null})} onBlur={e=>component.origin==="manual"&&void saveManualServiceLine(component,{shifts_per_month:e.target.value?Number(e.target.value):null})}/></label>
            </div>
            {component.productivity_reference&&<p className="fieldHint">Ставка из справочника «{component.productivity_reference.name.replace(/\bMVP\b/gi,"").trim()}»: {component.productivity_reference.value} {component.productivity_reference.unit}. Проверьте её и при необходимости замените.</p>}
            {!(component.productivity_m2_per_shift&&component.productivity_m2_per_shift>0)&&<p className="warning">{component.productivity_reference?"Введите положительную выработку для этой строки.":"В справочнике нет выработки для этого вида работ. Введите значение из вашего прайса или внутренней нормы."}</p>}
            <div className="areaSchedule">
              {component.schedule_status==="needs_input"&&<p className="warning">График в ТЗ не найден. Выберите режим уборки; если он не регулярный, укажите ожидаемое число смен.</p>}
              {component.schedule_warnings?.map((warning,index)=><p className="warning" key={index}>{warning}</p>)}
              {component.schedule_mode==="on_request"&&(component.shifts_per_month||0)<=0&&<p className="warning">ТЗ задаёт уборку по заявкам, но количество заявок в месяц не определено. Укажите ожидаемое число выездов.</p>}
            </div>
            {component.curation_warnings?.length?<p className="warning">Проверка строки: {component.curation_warnings.join("; ")}</p>:null}
          </div>)}
          {calc?.components?.length&&appSettings&&<div className="areaResults">
            <h3>Расчёт по адресам и видам работ</h3>
            <div className="areaResultsTable"><table><thead><tr><th>Адрес и вид работ</th><th>Площадь</th><th>Тариф и стоимость КП</th><th>Выработка</th><th>Режим</th><th>Смен/мес.</th><th>Часов/мес.</th><th>FTE</th><th>Сотрудников</th></tr></thead><tbody>
              {calc.components.map(component=><tr key={component.id}><td><b>{component.address}</b><small>{component.company_service_name||component.work_type}</small>{component.company_service_name&&component.company_service_name!==component.work_type&&<small>По ТЗ: {component.work_type}</small>}{component.origin==="manual"&&<small>Добавлено вручную</small>}</td><td>{fmt(component.area_m2,appSettings.display_locale,appSettings.display_number_max_fraction_digits)} м² {component.origin!=="manual"&&sourceArrow(component.source_document_id,component.source_location,`Открыть источник площади для адреса ${component.address}`,component.source_document_name)}</td><td>{fmt(component.price_per_m2_month??form?.service_price_per_m2_month??0,appSettings.display_locale,appSettings.display_currency_max_fraction_digits)} {appSettings.currency_unit_symbol}/м²/мес. · {fmt(component.monthly_price||0,appSettings.display_locale,appSettings.display_currency_max_fraction_digits)} {appSettings.currency_unit_symbol}/мес.</td><td>{component.productivity_m2_per_shift} м²/смену</td><td>{component.schedule_label} {component.origin!=="manual"&&sourceArrow(component.schedule_source_document_id,component.schedule_source_location,`Открыть источник режима для адреса ${component.address}`,component.schedule_source_document_name||"Источник режима")}</td><td>{fmt(component.shifts_per_month||0,appSettings.display_locale,appSettings.display_number_max_fraction_digits)}</td><td>{fmt(component.labor_hours_month||0,appSettings.display_locale,appSettings.display_number_max_fraction_digits)}</td><td>{fmt(component.fte||0,appSettings.display_locale,appSettings.display_number_max_fraction_digits)}</td><td>{component.physical_staff}</td></tr>)}
            </tbody></table></div>
            <p className="areaResultsTotal">Итого: {fmt(calc.total_area_m2||0,appSettings.display_locale,appSettings.display_number_max_fraction_digits)} м² · {fmt(calc.labor_hours_month,appSettings.display_locale,appSettings.display_number_max_fraction_digits)} чел.-часов/мес. · {calc.physical_staff_by_site} сотрудников</p>
          </div>}
        </div>}
        <label className="calculationConfirmation"><input type="checkbox" checked={calculationConfirmed} disabled={!calculationInputsReady} onChange={e=>setCalculationConfirmed(e.target.checked)}/><span><b>Подтверждаю расчёт целиком</b><small>Проверены площади и источники, режимы уборки, ставки выработки и параметры трудоёмкости. При их изменении подтверждение сбросится. Финансовые параметры можно менять и пересчитывать на вкладке «Экономика».</small></span></label>
        <button className="primary" disabled={!criticalReady} onClick={calculate}>Рассчитать трудоёмкость и экономику</button>
        {!form&&<p className="empty">Загрузка настроек расчёта…</p>}
        {!calculationInputsReady&&<p className="warning">{areaComponents.length?"Заполните отсутствующую выработку или задайте режим и количество смен для всех строк.":"Расчёт заблокирован: подтвердите площадь в карточке требований."}</p>}
        {calculationInputsReady&&!calculationConfirmed&&<p className="muted">После проверки всех строк поставьте единое подтверждение, чтобы запустить расчёт.</p>}
      </div>
    </section>}

    {active==="economics"&&<section className="panel">
      <div className="sectionHead"><div><h2>Экономика контракта</h2><p className="muted">Итоги по сделке и финансовым параметрам.</p></div></div>
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
          <div><span>Площадь по всем строкам</span><b>{appSettings?fmt(calc.total_area_m2||calc.area_m2||form?.area_m2||0,appSettings.display_locale,appSettings.display_number_max_fraction_digits)+" м²":(calc.total_area_m2||form?.area_m2||0)+" м²"}</b></div>
          <div><span>Трудозатраты в месяц</span><b>{appSettings?fmt(calc.labor_hours_month,appSettings.display_locale,appSettings.display_number_max_fraction_digits)+" ч":calc.labor_hours_month+" ч"}</b></div>
          <div><span>Штатная численность</span><b>{appSettings?fmt(calc.fte,appSettings.display_locale,appSettings.display_number_max_fraction_digits):calc.fte} FTE</b></div>
          <div><span>Сотрудников с замещением</span><b>{calc.physical_staff_by_site??calc.physical_staff}</b></div>
          <div><span>Выручка без НДС</span><b>{appSettings?money(calc.revenue_net,appSettings.display_locale,appSettings.currency_code,appSettings.display_currency_max_fraction_digits):calc.revenue_net}</b></div>
          <div><span>Полная себестоимость</span><b>{appSettings?money(calc.full_cost,appSettings.display_locale,appSettings.currency_code,appSettings.display_currency_max_fraction_digits):calc.full_cost}</b></div>
          <div><span>Прибыль</span><b>{appSettings?money(calc.profit,appSettings.display_locale,appSettings.currency_code,appSettings.display_currency_max_fraction_digits):calc.profit}</b></div>
          <div><span>Маржа</span><b className={appSettings&&calc.margin<appSettings.no_bid_margin_threshold?"badText":calc.margin<(form?.target_margin??calc.margin)?"warnText":"goodText"}>{appSettings?((calc.margin*appSettings.display_percentage_factor).toFixed(appSettings.display_percentage_decimal_places)+"%"):calc.margin}</b></div>
          <div><span>Тариф безубыточности</span><b>{appSettings?fmt(calc.break_even_price_per_m2,appSettings.display_locale,appSettings.display_number_max_fraction_digits)+" "+appSettings.currency_unit_symbol+"/м²":calc.break_even_price_per_m2}</b></div>
          <div><span>Тариф для цели</span><b>{appSettings?fmt(calc.target_price_per_m2,appSettings.display_locale,appSettings.display_number_max_fraction_digits)+" "+appSettings.currency_unit_symbol+"/м²":calc.target_price_per_m2}</b></div>
        </div>:<div className="empty">Сначала настройте и подтвердите исходные данные на вкладке «Трудоёмкость».</div>}
      </div>
      {calc&&<><div className={"decisionHero "+statusClass}><span>Коммерческое решение</span><b>{calc.decision}</b></div>{calc.conditions.length>0&&<div className="conditions"><h3>Условия</h3>{calc.conditions.map(c=><p key={c}>• {c}</p>)}</div>}</>}
      {calc&&appSettings&&<div className="sensitivity"><h3>Чувствительность к цене <button type="button" className="helpIcon" aria-label="Пояснить чувствительность к цене" title="Что показывает этот график?" onClick={()=>setSensitivityHelp(true)}>i</button></h3>{calc.sensitivity.map(s=><div key={s.delta} className="sens"><span>{s.delta===0?appSettings.base_sensitivity_label:((s.delta>0?"+":"")+Math.round(s.delta*appSettings.display_percentage_factor)+"%")}</span><i style={{width:String(Math.max(appSettings.sensitivity_bar_min_width,Math.min(appSettings.sensitivity_bar_max_width,(s.margin+appSettings.sensitivity_bar_margin_offset)*appSettings.sensitivity_bar_scale))+"%")}}></i><b>{(s.margin*appSettings.display_percentage_factor).toFixed(appSettings.display_percentage_decimal_places)+"%"}</b></div>)}</div>}
    </section>}

    {active==="proposal"&&<section className="panel proposalPanel">
      <div className="sectionHead"><div><h2>Коммерческое предложение</h2><p className="muted">Заполните реквизиты и скачайте редактируемый файл Word. В документ попадут подтверждённые требования и последний расчёт.</p></div></div>
       {!calc?<div className="empty">Сначала завершите и подтвердите расчёт на вкладке «Трудоёмкость».</div>:<>
         {(calculationDirty||!calculationConfirmed)&&<p className="warning">Расчёт устарел или требует подтверждения. Проверьте данные и пересчитайте сделку перед скачиванием КП.</p>}
        <p className="muted">Реквизиты заказчика подставлены из тендерных документов, если найдены. Стрелка рядом с полем открывает подтверждающий фрагмент; значения можно исправить вручную.</p>
        <div className="proposalForm">
          <label>Заказчик {organizationSource("customer_name","название заказчика")}<input value={proposalForm.customer_name} onChange={e=>updateProposalField("customer_name",e.target.value)} placeholder="Название организации"/></label>
          <label>Юридический адрес {organizationSource("customer_address","адрес заказчика")}<input value={proposalForm.customer_address} onChange={e=>updateProposalField("customer_address",e.target.value)} placeholder="Адрес заказчика"/></label>
          <label>ИНН {organizationSource("customer_inn","ИНН заказчика")}<input value={proposalForm.customer_inn} onChange={e=>updateProposalField("customer_inn",e.target.value)} placeholder="ИНН"/></label>
          <label>КПП {organizationSource("customer_kpp","КПП заказчика")}<input value={proposalForm.customer_kpp} onChange={e=>updateProposalField("customer_kpp",e.target.value)} placeholder="КПП"/></label>
          <label>ОГРН {organizationSource("customer_ogrn","ОГРН заказчика")}<input value={proposalForm.customer_ogrn} onChange={e=>updateProposalField("customer_ogrn",e.target.value)} placeholder="ОГРН"/></label>
          <label>Представитель заказчика {organizationSource("customer_contact_person","представитель заказчика")}<input value={proposalForm.customer_contact_person} onChange={e=>updateProposalField("customer_contact_person",e.target.value)} placeholder="Фамилия, имя, отчество"/></label>
          <label>Телефон заказчика {organizationSource("customer_phone","телефон заказчика")}<input value={proposalForm.customer_phone} onChange={e=>updateProposalField("customer_phone",e.target.value)} placeholder="Телефон"/></label>
          <label>Электронная почта заказчика {organizationSource("customer_email","электронная почта заказчика")}<input value={proposalForm.customer_email} onChange={e=>updateProposalField("customer_email",e.target.value)} placeholder="Почта"/></label>
          <label>Исполнитель<input value={proposalForm.supplier_name} onChange={e=>updateProposalField("supplier_name",e.target.value)} placeholder="Название вашей организации"/></label>
          <label>Контакты исполнителя<input value={proposalForm.contact_details} onChange={e=>updateProposalField("contact_details",e.target.value)} placeholder="Телефон, почта"/></label>
          <label>Срок действия, дней<input type="number" min="1" max="365" value={proposalForm.validity_days} onChange={e=>updateProposalField("validity_days",Number(e.target.value))}/></label>
          <label className="proposalWide">Дополнительные условия<textarea rows={3} value={proposalForm.additional_terms} onChange={e=>updateProposalField("additional_terms",e.target.value)} placeholder="Условия оплаты, сроки начала работ и другие согласованные детали"/></label>
        </div>
        <div className="proposalPreview"><h3>Предварительный состав КП</h3><p><b>{proposalForm.customer_name||"[указать заказчика]"}</b> · {proposalForm.supplier_name||"[указать исполнителя]"}</p><p>{calc.components?.length||areaComponents.length} строк адресов и видов работ · {fmt(calc.total_area_m2||calc.components?.reduce((sum,item)=>sum+item.area_m2,0)||form?.area_m2||0,appSettings?.display_locale||"ru-RU",appSettings?.display_number_max_fraction_digits||1)} м²</p><p>Стоимость: {appSettings?money(calc.revenue_with_vat,appSettings.display_locale,appSettings.currency_code,appSettings.display_currency_max_fraction_digits):calc.revenue_with_vat} в месяц · срок {proposalContractMonths} мес.</p><p>За весь срок: {appSettings?money(calc.components?.length?calc.components.reduce((sum,item)=>sum+(item.contract_price||0),0):calc.revenue_with_vat*proposalContractMonths,appSettings.display_locale,appSettings.currency_code,appSettings.display_currency_max_fraction_digits):calc.components?.reduce((sum,item)=>sum+(item.contract_price||0),0)||calc.revenue_with_vat*proposalContractMonths}</p><p className="muted">Данные КП проверяются отдельно от внутренней экономики: маржа и себестоимость в файл не включаются.</p></div>
         <button className="primary" disabled={busy||calculationDirty||!calculationConfirmed} onClick={downloadProposal}>Скачать проект КП (.docx)</button>
      </>}
    </section>}

    {active==="settings"&&<section className="panel formulaSettingsPanel">
      <div className="settingsSwitcher" role="tablist" aria-label="Настройки компании">
        <button type="button" role="tab" aria-selected={priceListView==="catalog"} className={priceListView==="catalog"?"selected":""} onClick={()=>setPriceListView("catalog")}>Прайс-лист услуг</button>
        <button type="button" role="tab" aria-selected={priceListView==="demo"} className={priceListView==="demo"?"selected":""} onClick={()=>setPriceListView("demo")}>Тарифы исполнителей</button>
        <button type="button" role="tab" aria-selected={priceListView==="formulas"} className={priceListView==="formulas"?"selected":""} onClick={()=>setPriceListView("formulas")}>Формулы расчёта</button>
      </div>
      {priceListView==="catalog"?<div className="companyPriceList">
        <div className="sectionHead"><div><h2>Прайс-лист компании</h2><p className="muted">Выберите услугу в требованиях, чтобы подставить её описание, тариф и норматив. Тарифы из этого списка используются в расчёте и проекте КП.</p></div></div>
        <div className="priceListDraft">
          <label>Название в списке<input value={priceListDraft.name} onChange={e=>setPriceListDraft({...priceListDraft,name:e.target.value})} placeholder="Комплексная уборка помещений"/></label>
          <label>Вид площади<input value={priceListDraft.area_type} onChange={e=>setPriceListDraft({...priceListDraft,area_type:e.target.value})} placeholder="Помещения, территория"/></label>
          <label>Вид работ / описание для КП<input value={priceListDraft.work_type} onChange={e=>setPriceListDraft({...priceListDraft,work_type:e.target.value})} placeholder="Состав работ или услуга"/></label>
          <label>Тариф, {appSettings?.currency_unit_symbol??"₽"}/м²/мес<input type="number" min="0" step="any" value={priceListDraft.price_per_m2_month} onChange={e=>setPriceListDraft({...priceListDraft,price_per_m2_month:e.target.value})}/></label>
          <label>Норматив, м²/смену<input type="number" min="0" step="any" value={priceListDraft.productivity_m2_per_shift} onChange={e=>setPriceListDraft({...priceListDraft,productivity_m2_per_shift:e.target.value})} placeholder="Необязательно"/></label>
          <label>Примечание<input value={priceListDraft.notes} onChange={e=>setPriceListDraft({...priceListDraft,notes:e.target.value})} placeholder="Условия, состав или ограничение тарифа"/></label>
          <button className="primary" type="button" disabled={priceListBusy} onClick={()=>void createPriceListItem()}>{priceListBusy?"Сохраняю…":"Добавить в прайс-лист"}</button>
        </div>
        {priceListItems.length===0?<div className="empty">Прайс-лист пока пуст. Добавьте первую услугу выше.</div>:<div className="priceListRows">{priceListItems.map(item=><article className={"priceListRow "+(!item.is_active?"archived":"")} key={item.id}>
          <div className="priceListRowHead"><b>{item.name||"Новая услуга"}</b><span>{item.is_active?"Доступна для выбора":"В архиве"}</span><button type="button" disabled={priceListBusy} onClick={()=>void savePriceListItem(item.id,{name:item.name})}>{priceListBusy?"Сохраняю…":priceListSavedId===item.id?"Название сохранено":"Сохранить название"}</button><button type="button" disabled={priceListBusy} onClick={()=>void archivePriceListItem(item)}>{item.is_active?"В архив":"Вернуть в прайс"}</button></div>
          <div className="priceListFields">
            <label>Название услуги<input value={item.name} onChange={e=>{setPriceListSavedId(null);setPriceListItems(current=>current.map(row=>row.id===item.id?({...row,name:e.target.value}):row))}} onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();void savePriceListItem(item.id,{name:item.name})}}}/></label>
            <label>Вид площади<input value={item.area_type} onChange={e=>setPriceListItems(current=>current.map(row=>row.id===item.id?({...row,area_type:e.target.value}):row))} onBlur={e=>void savePriceListItem(item.id,{area_type:e.target.value})}/></label>
            <label>Вид работ<input value={item.work_type} onChange={e=>setPriceListItems(current=>current.map(row=>row.id===item.id?({...row,work_type:e.target.value}):row))} onBlur={e=>void savePriceListItem(item.id,{work_type:e.target.value})}/></label>
            <label>Тариф, {appSettings?.currency_unit_symbol??"₽"}/м²/мес<input type="number" min="0" step="any" value={item.price_per_m2_month} onChange={e=>setPriceListItems(current=>current.map(row=>row.id===item.id?({...row,price_per_m2_month:e.target.value?Number(e.target.value):0}):row))} onBlur={e=>void savePriceListItem(item.id,{price_per_m2_month:Number(e.target.value)})}/></label>
            <label>Норматив, м²/смену<input type="number" min="0" step="any" value={item.productivity_m2_per_shift??""} placeholder="Не задан" onChange={e=>setPriceListItems(current=>current.map(row=>row.id===item.id?({...row,productivity_m2_per_shift:e.target.value?Number(e.target.value):null}):row))} onBlur={e=>void savePriceListItem(item.id,{productivity_m2_per_shift:e.target.value?Number(e.target.value):null})}/></label>
            <label>Примечание<input value={item.notes??""} onChange={e=>setPriceListItems(current=>current.map(row=>row.id===item.id?({...row,notes:e.target.value||null}):row))} onBlur={e=>void savePriceListItem(item.id,{notes:e.target.value.trim()||null})}/></label>
          </div>
        </article>)}</div>}
        {calculationDirty&&calc&&<p className="warning">В прайс-листе есть изменения. Текущий расчёт сохранён по прежним тарифам — пересчитайте его, чтобы обновить КП.</p>}
      </div>:priceListView==="demo"?<div className="companyPriceList">
        <div className="sectionHead"><div><h2>Справочник тарифов исполнителей</h2><p className="muted">Внешние ставки для сравнения с прайсом компании. Откройте источник и проверьте единицы, период и условия перед тем, как учитывать тариф при подготовке предложения.</p></div></div>
        <div className="demoTariffNotice">В расчёт и проект КП подставляются услуги из вкладки «Прайс-лист услуг». Тарифы исполнителей помогают сравнить рыночные условия; единицы и период могут отличаться.</div>
        <label className="demoTariffSearch">Поиск по исполнителю, объекту или услуге<input value={demoTariffQuery} onChange={event=>setDemoTariffQuery(event.target.value)} placeholder="Например, офис или генеральная уборка"/></label>
        {demoProviderTariffs&&<div className="demoFeatured"><h3>Несколько примеров для быстрого просмотра</h3><div className="demoFeaturedRows">{demoProviderTariffs.items.filter(item=>demoProviderTariffs.featured_ids.includes(item.id)).map(item=><article className="demoFeaturedRow" key={item.id}>
          <div><b>{item.provider}</b><span>{item.object_type} · {item.service}</span></div>
          <strong>{item.price_min===null?"Договорная":item.price_max===null?`от ${fmt(item.price_min,"ru-RU",2)}`:`${fmt(item.price_min,"ru-RU",2)}–${fmt(item.price_max,"ru-RU",2)}`} {item.price_unit}</strong>
          <small>{item.area_range?`Диапазон площади: ${item.area_range} м² · `:""}{item.details&&`${item.details} `}{item.evidence}</small>
          <a href={item.source_url} target="_blank" rel="noreferrer">Источник ↗</a>
        </article>)}</div></div>}
        {demoProviderTariffs&&[...new Set(demoProviderTariffs.items.map(item=>item.provider))].map(provider=>{
          const query=demoTariffQuery.trim().toLocaleLowerCase("ru-RU");
          const entries=demoProviderTariffs.items.filter(item=>item.provider===provider&&(!query||[item.provider,item.city,item.object_type,item.service,item.area_range||""].join(" ").toLocaleLowerCase("ru-RU").includes(query)));
          if(!entries.length)return null;
          return <details className="demoTariffProvider" key={provider}>
            <summary><b>{provider}</b><span>{entries[0].city} · {entries.length} тарифов</span></summary>
            <div className="demoTariffRows">{entries.map(item=><article className="demoTariffRow" key={item.id}>
              <div><b>{item.object_type}</b><span>{item.service}</span></div>
              <div>{item.area_range&&<small>Площадь: {item.area_range} м²</small>}<strong>{item.price_min===null?"Договорная":item.price_max===null?`от ${fmt(item.price_min,"ru-RU",2)}`:`${fmt(item.price_min,"ru-RU",2)}–${fmt(item.price_max,"ru-RU",2)}`} {item.price_unit}</strong></div>
              <div className="demoTariffSource"><small>{item.details&&`${item.details} `}{item.evidence} Набор данных: {item.source_dataset}. Дата извлечения: {item.source_date}.</small><a href={item.source_url} target="_blank" rel="noreferrer">Открыть источник ↗</a></div>
            </article>)}</div>
          </details>;
        })}
      </div>:<>
        <div className="sectionHead"><div><h2>Формулы расчёта</h2><p className="muted">Просматривайте и изменяйте формулы трудозатрат, себестоимости, тарифа КП и маржинальности. Новые формулы применяются при следующем пересчёте.</p></div></div>
        <div className="formulaNotice"><b>Формула маржинальности:</b> прибыль ÷ выручка без НДС. Внутри расчёта используется доля: `0.2` означает `20%`. Разрешены числа, указанные переменные, скобки и операции `+ − * /`; произвольный код не выполняется.</div>
        <div className="formulaList">{formulaSettings.map(item=><details className="formulaSetting" key={item.key} open={item.key==="margin"}>
          <summary><b>{item.label}</b><code>{item.key}</code></summary>
          <p>{item.description}</p>
          <label>Формула<input value={item.expression} onChange={event=>setFormulaSettings(current=>current.map(formula=>formula.key===item.key?({...formula,expression:event.target.value}):formula))}/></label>
          <small>Доступные переменные: {item.variables.join(", ")}</small>
        </details>)}</div>
        <div className="formulaActions">
          <button className="primary" disabled={formulaBusy||formulaSettings.length===0} onClick={()=>void saveCalculationFormulas()}>{formulaBusy?"Сохраняю…":"Сохранить формулы"}</button>
          <button type="button" disabled={formulaBusy||formulaSettings.length===0} onClick={()=>setFormulaSettings(current=>current.map(item=>({...item,expression:item.default_expression})))}>Восстановить исходные формулы</button>
          <button type="button" onClick={()=>setActive(calc?"economics":"workforce")}>Перейти к пересчёту →</button>
        </div>
        {calculationDirty&&calc&&<p className="warning">Формулы сохранены. Результат показывает предыдущий расчёт — запустите пересчёт на вкладке «Экономика».</p>}
      </>}
    </section>}

    {active==="pipeline"&&<section className="panel">
      <h2>Пошаговый контроль обработки</h2>
      <p className="muted">Для каждого шага доступны вход, выход, длительность и предупреждения.</p>
      {runs.length===0?<div className="empty">Пока нет запусков.</div>:runs.map(run=><div className="run" key={run.id}><h3>{"Запуск #"+run.id+" · "+run.status}</h3>{run.steps.map((s,i)=><details className={"step "+s.status} key={i}><summary><span>{(s.status==="success"?"✓":s.status==="failed"?"✕":"○")+" "+s.name}</span><small>{s.duration_ms?String(s.duration_ms)+" ms":""}</small></summary><div className="stepBody">{s.warnings?.map(w=><p className="warning" key={w}>{w}</p>)}<div className="json"><b>Вход</b><pre>{JSON.stringify(s.input,null,2)}</pre></div><div className="json"><b>Выход</b><pre>{JSON.stringify(s.output,null,2)}</pre></div></div></details>)}</div>)}
    </section>}
        {active!=="pipeline"&&active!=="settings"&&<nav className="stageNav" aria-label="Переход между этапами">
          <button type="button" onClick={()=>moveStage(-1)} disabled={stageIndex<=0}>← Назад</button>
          <span>Этап {stageIndex+1} из {tabs.length}</span>
          <button type="button" className="primary" onClick={()=>moveStage(1)} disabled={stageIndex>=tabs.length-1}>Далее →</button>
        </nav>}
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
            <p>{fmt(productivityHelp.area_m2,appSettings.display_locale,appSettings.display_number_max_fraction_digits)} м² ÷ {fmt(productivityHelpNumbers.rate,appSettings.display_locale,appSettings.display_number_max_fraction_digits)} м²/смену = <b>{fmt(productivityHelpNumbers.employeeShiftsPerVisit,appSettings.display_locale,2)} смены сотрудника на одну уборку</b>; при {fmt(appSettings.hours_per_shift,appSettings.display_locale,1)} часах в смене это около <b>{fmt(productivityHelpNumbers.hoursPerVisit,appSettings.display_locale,1)} чел.-часа</b>.</p>
            {productivityHelpNumbers.hoursPerMonth!==null&&<p>По режиму «{productivityHelp.schedule_label}» ({fmt(productivityHelpNumbers.monthlyVisits??0,appSettings.display_locale,1)} смен/выездов в месяц): <b>{fmt(productivityHelpNumbers.hoursPerMonth,appSettings.display_locale,1)} чел.-часа/мес.</b> · {fmt(productivityHelpNumbers.fte??0,appSettings.display_locale,2)} штатной единицы до коэффициента замещения.</p>}
            {productivityHelpNumbers.hoursPerMonth===null&&<p className="warning">Месячный итог появится после ввода числа выездов или смен.</p>}
          </div>}
          {!productivityHelpNumbers&&<p className="warning">Чтобы показать расчёт для этой строки, введите положительную выработку в поле.</p>}
          <p className="muted">Чем выше ставка, тем меньше расчётные затраты времени. Она зависит от вида работ, механизации и условий объекта.</p>
          {productivityHelp.productivity_reference&&<p className="modalNote">Источник ставки: «{productivityHelp.productivity_reference.name.replace(/\bMVP\b/gi,"").trim()}». Сверьте её с прайсом или внутренней нормой.</p>}
          {!productivityHelp.productivity_reference&&<p className="modalNote">Ставка введена вручную. Используйте значение из прайса, внутренней нормы или хронометража.</p>}
          <button type="button" className="primary modalAction" onClick={()=>setProductivityHelp(null)}>Понятно</button>
        </section>
      </div>}
      {sensitivityHelp&&<div className="modalBackdrop" role="presentation" onMouseDown={event=>{if(event.target===event.currentTarget)setSensitivityHelp(false)}}>
        <section className="helpModal" role="dialog" aria-modal="true" aria-labelledby="sensitivity-modal-title">
          <button type="button" className="modalClose" aria-label="Закрыть пояснение" onClick={()=>setSensitivityHelp(false)}>×</button>
          <p className="modalEyebrow">ПОЯСНЕНИЕ К РАСЧЁТУ</p><h2 id="sensitivity-modal-title">Чувствительность к цене</h2>
          <p>График показывает, как меняется маржа, если месячный тариф за квадратный метр отклонить от текущего.</p>
          <ul><li>«База» — маржа при введённом тарифе.</li><li>Значения со знаком минус показывают снижение тарифа, со знаком плюс — повышение.</li><li>Проценты справа — расчётная маржа после такого изменения.</li></ul>
          <button type="button" className="primary modalAction" onClick={()=>setSensitivityHelp(false)}>Понятно</button>
        </section>
      </div>}
    </main>
  </div>
}
