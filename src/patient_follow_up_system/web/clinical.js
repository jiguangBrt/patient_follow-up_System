const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("doctorToken");
let current = null;
let patients = [];
let previewUrl = null;
let previewSequence = 0;
const editors = new Map();
const stateNames = {not_run:"尚未运行 OCR，可提取或手工录入",ready:"候选已提取，等待逐字段人工确认",manual:"未提取到可用字段，请对照原件手工录入",failed:"OCR 失败，请重试或手工录入"};
const statusNames = {buffered:"缓冲区 · 未绑定患者",filed:"已入档",rejected:"已驳回"};
function message(text, error=false) { $("message").textContent=text; $("message").className=`status ${error?"error":"success"}`; }
async function api(path, options={}) {
  const response=await fetch(path,{...options,headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`}});
  const data=await response.json();
  if(!response.ok) throw new Error(response.status===401?"登录已失效或账号已停用，请返回医生工作台重新登录。":typeof data.detail==="string"?data.detail:"请检查输入内容");
  return data;
}
function button(text, action) { const el=document.createElement("button"); el.type="button"; el.textContent=text; el.className="secondary"; el.onclick=async()=>{el.disabled=true;try{await action();}catch(e){message(e.message,true);}finally{el.disabled=false;}}; return el; }
async function list() {
  const documents=await api("/clinical-documents");
  $("documents").replaceChildren(...documents.map(doc=>{
    const row=document.createElement("div"); row.className="patient";
    const text=document.createElement("span"); text.textContent=`${doc.candidate_name?`候选姓名：${doc.candidate_name}`:"姓名待识别/核对"} · ${doc.original_name} · ${statusNames[doc.status]} · ${doc.pending_fields} 项待确认`;
    row.append(text,button("打开逐字段审核",()=>open(doc.id))); return row;
  }));
  if(!documents.length) $("documents").textContent="暂无病例，请先上传原件。";
}
async function preview(page, evidence=null) {
  const sequence=++previewSequence;
  const response=await fetch(`/clinical-documents/${current.id}/pages/${page}`,{headers:{Authorization:`Bearer ${token}`}});
  if(!response.ok) { if(sequence===previewSequence) {$("preview").removeAttribute("src");$("highlight").classList.add("hidden");message("预览不可用，请打开原件手工核对。",true);} return; }
  const blob=await response.blob(); if(sequence!==previewSequence) return;
  if(previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl=URL.createObjectURL(blob); $("preview").src=previewUrl;
  $("previewPage").value=String(page); $("highlight").classList.toggle("hidden",!evidence);
  if(evidence) {
    const [x0,y0,x1,y1]=evidence.box;
    Object.assign($("highlight").style,{left:`${x0*100}%`,top:`${y0*100}%`,width:`${(x1-x0)*100}%`,height:`${(y1-y0)*100}%`});
    $("evidenceText").textContent=`第 ${page} 页原文：${evidence.text}`;
  } else $("evidenceText").textContent="点击字段的“定位原文”查看对应证据。";
}
async function open(id) {
  current=await api(`/clinical-documents/${id}`);
  history.replaceState(null,"",`/clinical?id=${id}`);
  render(); await preview(1); $("reviewCard").scrollIntoView({behavior:"smooth",block:"start"});
}
function render() {
  const doc=current; editors.clear();
  $("reviewCard").classList.remove("hidden"); $("reviewTitle").textContent=`${doc.original_name} · ${statusNames[doc.status]}`;
  $("documentMeta").textContent=`资料 #${doc.id} · 版本 ${doc.version} · ${doc.document_type} · ${doc.extraction_version||"人工录入"} · 原件 SHA-256：${doc.sha256}`;
  $("extractionState").textContent=doc.extraction_error||stateNames[doc.extraction_status];
  $("previewPage").replaceChildren(...Array.from({length:Math.max(1,doc.pages.length)},(_,i)=>new Option(`第 ${i+1} 页`,String(i+1))));
  $("fields").replaceChildren(...doc.fields.map(field=>{
    const row=document.createElement("article"); row.className="field-review";
    const heading=document.createElement("h3"); heading.textContent=field.label;
    const candidate=document.createElement("p"); candidate.className="candidate";
    const quality={missing:"未识别/未提供",conflict:"存在冲突，请人工核对",low_confidence:"低可信，请人工核对",recognized:"识别候选"}[field.candidate_status];
    candidate.textContent=`${quality}${field.confidence==null?"":` · OCR 置信度 ${Math.round(field.confidence*100)}%`}\n${field.candidate_value||"未知"}`;
    const value=document.createElement("textarea"); value.setAttribute("aria-label",`${field.label}确认值`); value.maxLength=10000; value.value=field.confirmed_value??field.candidate_value??"";
    const select=document.createElement("select"); select.setAttribute("aria-label",`${field.label}审核状态`);
    [ ["pending","待确认（暂不入档）"],["confirmed","原值确认"],["corrected","修改后确认/手工录入"] ].forEach(([v,t])=>select.add(new Option(t,v)));
    select.value=field.review_status;
    const locked=doc.status==="rejected"||(doc.status==="filed"&&field.review_status!=="pending"); select.disabled=locked; value.disabled=locked;
    value.oninput=()=>{ if(select.value==="confirmed"&&value.value!==field.candidate_value) select.value="corrected"; };
    row.append(heading,candidate,value,select);
    const evidence=document.createElement("div"); evidence.className="row";
    field.evidence.forEach((item,index)=>evidence.append(button(`定位原文 ${index+1}（第${item.page}页）`,async()=>{await preview(item.page,item);$("previewWrap").scrollIntoView({behavior:"smooth",block:"center"});})));
    row.append(evidence); editors.set(field.key,{value,select,locked}); return row;
  }));
  const target=$("targetPatient"); target.replaceChildren(new Option("请人工选择，不按识别姓名自动匹配",""),new Option("按已确认姓名新建患者档案","new"));
  patients.forEach(p=>target.add(new Option(`${p.display_name} · ${p.patient_code}`,String(p.id))));
  if(doc.patient_id) target.value=String(doc.patient_id);
  target.disabled=doc.status!=="buffered";
  $("fileRecord").disabled=doc.status!=="buffered"; $("reject").disabled=doc.status!=="buffered"; $("save").disabled=doc.status==="rejected";
  $("extract").disabled=doc.status!=="buffered"||doc.fields.some(f=>f.review_status!=="pending");
  $("historyText").classList.add("hidden");
}
async function review(action) {
  const fields=[...editors].filter(([,e])=>!e.locked).map(([key,e])=>({key,review_status:e.select.value,confirmed_value:e.select.value==="pending"?null:e.value.value.trim()}));
  const target=$("targetPatient").value;
  const payload={version:current.version,action,fields,create_patient:action==="file"&&target==="new",patient_id:action==="file"&&target&&target!=="new"?Number(target):null};
  if(action==="file"&&!target) throw new Error("请先选择确认入档患者或明确新建档案。");
  current=await api(`/clinical-documents/${current.id}/review`,{method:"POST",body:JSON.stringify(payload)});
  patients=await api("/patients"); render(); await list();
  message(action==="file"?"已按确认姓名归入患者档案。待确认字段仍留在审核区。":action==="reject"?"整份资料已驳回，原件和审核记录已保留。":"逐字段审核已保存，尚未确认的值不会进入正式档案。");
}
$("uploadForm").onsubmit=async event=>{
  event.preventDefault(); const btn=$("uploadButton");btn.disabled=true;
  try { const file=$("file").files[0];if(!file) return;if(file.size>8*1024*1024) throw new Error("请选择 8 MB 以内的文件。");
    const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(",")[1]);reader.onerror=reject;reader.readAsDataURL(file);});
    const doc=await api("/clinical-documents",{method:"POST",body:JSON.stringify({document_name:file.name,document_mime_type:file.type,document_base64:encoded})});
    event.target.reset();await list();await open(doc.id);message("原件已保存在缓冲区。点击“运行本机 OCR”提取候选字段，或直接手工录入。");
  }catch(e){message(e.message,true);}finally{btn.disabled=false;}
};
function bind(id,action){$(id).onclick=async()=>{const btn=$(id);btn.disabled=true;try{await action();}catch(e){message(e.message,true);}finally{if(current) renderButtonState();else btn.disabled=false;}};}
function renderButtonState(){ $("extract").disabled=current.status!=="buffered"||current.fields.some(f=>f.review_status!=="pending");$("save").disabled=current.status==="rejected";$("fileRecord").disabled=current.status!=="buffered";$("reject").disabled=current.status!=="buffered";$("refresh").disabled=false;$("openOriginal").disabled=false;$("history").disabled=false; }
bind("extract",async()=>{message("正在本机识别，请稍候…");current=await api(`/clinical-documents/${current.id}/extract`,{method:"POST",body:JSON.stringify({version:current.version})});render();await preview(1);await list();message(stateNames[current.extraction_status],current.extraction_status==="failed");});
bind("save",()=>review("save"));bind("fileRecord",()=>review("file"));bind("reject",()=>review("reject"));
bind("refresh",async()=>{await list();message("缓冲区已刷新；打开资料可加载最新审核版本。");});
bind("openOriginal",async()=>{const response=await fetch(`/clinical-documents/${current.id}/file`,{headers:{Authorization:`Bearer ${token}`}});if(!response.ok)throw new Error("原件不可用或登录已失效");const url=URL.createObjectURL(await response.blob());window.open(url,"_blank","noopener");setTimeout(()=>URL.revokeObjectURL(url),60000);});
bind("history",async()=>{const events=await api(`/clinical-documents/${current.id}/history`);$("historyText").textContent=JSON.stringify(events,null,2);$("historyText").classList.remove("hidden");});
$("previewPage").onchange=()=>preview(Number($("previewPage").value));
$("logout").onclick=()=>{sessionStorage.removeItem("doctorToken");location.href="/doctor";};
async function init(){try{if(!token)throw new Error("请从左侧患者管理返回医生工作台登录。");const me=await api("/auth/me");if(me.role!=="doctor")throw new Error("请使用医生账号。");DoctorShell.setUser(me.display_name);patients=await api("/patients");await list();const params=new URLSearchParams(location.search);
  if(params.get("source")&&params.get("id")){const doc=await api("/clinical-documents/import",{method:"POST",body:JSON.stringify({source_kind:params.get("source"),source_id:Number(params.get("id"))})});await open(doc.id);await list();}
  else if(params.get("id"))await open(Number(params.get("id")));message("缓冲区候选不会自动绑定患者，请核对姓名及每项内容。");
}catch(e){message(e.message,true);}}
init();
