const $ = id => document.getElementById(id);
const staffRole = AppSession.staffRole();
const isStudent = staffRole === "student";
let token = AppSession.require(staffRole);
let patientPermissions = [];
let doctorPatients = [];
let selectedPatientId = null;
let doctorId = null;
let selectionEpoch = 0;
let currentInvitationId = null;
let openNewPatientAfterView = false;
const stateNames = {enrolled:"已建档",pending:"等待医生审核", approved:"已批准", rejected:"已驳回", buffered:"待医生确认", filed:"已归档"};
function node(tag, text, className) { const el=document.createElement(tag); if(text!=null)el.textContent=text; if(className)el.className=className; return el; }
function message(text,error=false) { $("message").textContent=text; $("message").className=`status ${error?"error":"success"}`; }
async function api(path,options={}) {
  const response=await AppPaths.fetch(path,{...options,headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`}});
  const data=await response.json();
  if(!response.ok){if(response.status===401)AppSession.logout(staffRole,true);throw new Error(typeof data.detail==="string"?data.detail:`请求失败（${response.status}）`);}
  return data;
}
function actionButton(text,action,secondary=false) {
  const button=node("button",text,secondary?"secondary":""); button.type="button";
  button.onclick=async()=>{button.disabled=true;try{await action();}catch(error){message(error.message,true);}finally{button.disabled=false;}};
  return button;
}
function detailLine(label,value) {const p=node("p");p.append(node("strong",`${label}：`),document.createTextNode(value));return p;}
function showModal(id) {const modal=$(id);modal.classList.remove("hidden");if(!modal.open)modal.showModal();}
function closeModal(id) {if($(id).open)$(id).close();$(id).classList.add("hidden");}
function activateDoctorView() {
  const views={patients:["患者管理","诊疗管理","patientsCard"],intakes:["建档申请","诊疗管理","intakesCard"],notice:["患者须知","设置","noticeCard"],followups:["随访计划","随访与科研","placeholderCard","随访节点与复诊提醒将在这里管理。"],cohorts:["科研队列","随访与科研","placeholderCard","研究分组与队列将在这里管理。"],exports:["资料导出","随访与科研","placeholderCard","资料导出将在这里提供。"]};
  const key=Object.hasOwn(views,location.hash.slice(1))?location.hash.slice(1):"patients";
  const [title,group,card,description]=views[key];
  ["patientsCard","intakesCard","noticeCard","placeholderCard"].forEach(id=>$(id).classList.toggle("hidden",id!==card));
  closeModal("inviteCard");closeModal("newPatientCard");document.body.classList.toggle("patients-view",key==="patients");
  $("pageTitle").textContent=title;$("breadcrumb").textContent=`${group} / ${title}`;DoctorShell.activate(key);$("message").classList.add("hidden");
  if(description){$("placeholderTitle").textContent=title;$("placeholderDescription").textContent=description;}
  if(key==="intakes")loadIntakes();
  if(key==="patients"&&openNewPatientAfterView){openNewPatientAfterView=false;$("showNewPatient").click();}
}
function renderPatients() {
  const query=$("patientSearch").value.trim().toLowerCase();const items=doctorPatients.filter(p=>`${p.display_name} ${p.patient_code}`.toLowerCase().includes(query));
  $("patientCounts").textContent=`共 ${doctorPatients.length} 位患者`;
  $("patients").replaceChildren(...items.map(patient=>{
    const button=actionButton(patient.display_name,()=>selectPatient(patient.id));button.className=`patient-name-button ${patient.id===selectedPatientId?"selected":""}`;
    button.setAttribute("aria-pressed",String(patient.id===selectedPatientId));button.dataset.patientId=patient.id;button.title=patient.patient_code;return button;
  }));
  if(!items.length)$("patients").append(node("p",query?"没有匹配的患者":isStudent?"暂无可查看患者，请联系所属医生。":"暂无患者，请先新增患者。","muted"));
}
async function loadPatients(preferred=selectedPatientId) {
  doctorPatients=await api("/patients");
  const stored=Number(AppPaths.storage.getItem(`selectedPatient:${doctorId}`));
  const chosen=doctorPatients.find(p=>p.id===preferred)||doctorPatients.find(p=>p.id===stored)||doctorPatients[0];
  if(chosen)await selectPatient(chosen.id);
  else {
    selectedPatientId=null;selectionEpoch++;AppPaths.storage.removeItem(`selectedPatient:${doctorId}`);renderPatients();$("patientHeading").textContent="还没有患者";$("patientMeta").textContent="请从左侧新增患者，开始建档与资料整理。";
    $("showPatientQr").disabled=true;$("refreshPatient").disabled=true;$("showGastritis").disabled=true;$("patientDetailScroll").replaceChildren(emptyState("暂无患者档案","点击“新增患者”，填写姓名后即可生成专属建档二维码。"));
  }
}
function emptyState(title,description) {const el=node("div",null,"patient-empty");el.append(node("h2",title),node("p",description));return el;}
async function selectPatient(id) {
  const patient=doctorPatients.find(p=>p.id===id);if(!patient)return;
  $("showGastritis").disabled=true;$("showGastritis").dataset.patientId="";const changed=selectedPatientId!==id;selectedPatientId=id;const epoch=++selectionEpoch;
  AppPaths.storage.setItem(`selectedPatient:${doctorId}`,String(id));closeModal("inviteCard");currentInvitationId=null;renderPatients();
  $("patientHeading").textContent=patient.display_name;$("patientMeta").textContent="";$("showPatientQr").disabled=false;$("refreshPatient").disabled=false;
  const pane=$("patientDetailScroll");const position=changed?0:pane.scrollTop;pane.replaceChildren(node("p","正在加载患者资料…","muted"));
  try {
    const data=await api(`/patients/${id}/workspace`);if(epoch!==selectionEpoch||selectedPatientId!==id)return;
    patientPermissions=data.permissions||(isStudent?[]:["view","edit","review"]);
    $("showGastritis").dataset.patientId=String(id);$("showGastritis").dataset.permissions=patientPermissions.join(",");$("showGastritis").disabled=false;const profile=data.profile;
    const birth=profile?.date_of_birth?profile.date_of_birth.split("-").map(Number).join("-"):"";
    $("patientMeta").textContent=profile?[profile.sex,birth,profile.operator_relationship,profile.phone].filter(Boolean).join(" · "):"";
    pane.replaceChildren();
    const overview=node("div",null,"patient-overview");overview.append(node("span",profile?`建档状态：${stateNames[profile.status]||profile.status} · 须知版本 ${profile.notice_version||"未记录"}`:"患者扫码后可填写基本信息并补交病历。"));
    if(isStudent)overview.append(node("span",`我的权限：${patientPermissions.map(p=>({view:"查看",edit:"录入",review:"审核"})[p]).join("、")} · 到期或撤销后失效`));
    if(profile?.status==="pending"&&patientPermissions.includes("review"))overview.append(actionButton("审核建档申请",()=>{location.hash="intakes";},true));
    pane.append(overview);
    if(data.unfiled.length)pane.append(unfiledModule(data.unfiled));
    data.visits.forEach(visit=>pane.append(visitModule(visit)));
    if(!data.visits.length)pane.append(emptyState("暂无已归档就诊","病历识别后请核对就诊日期并确认归档，同一天的资料会自动合并展示。"));
    pane.scrollTop=position;
  }catch(error){if(epoch===selectionEpoch)pane.replaceChildren(emptyState("资料暂时无法加载",error.message));}
}
function moduleShell(title,count,className="visit-module") {
  const section=node("section",null,className);const head=node("div",null,"visit-module-heading");head.append(node("h2",title),node("span",count));section.append(head);return section;
}
function clinicalUrl(item) {return item.kind==="clinical"?`/clinical?id=${item.id}`:`/clinical?source=${item.kind}&id=${item.id}`;}
function visitModule(visit) {
  const section=moduleShell(visit.date?`${visit.date} · 就诊记录`:"日期待确认 · 历史就诊",`${visit.records.length} 份记录 · 已归档`);
  visit.records.forEach(record=>{
    const article=node("article",null,"record-content");article.append(node("h3",record.original_name||record.label||"就诊资料"));
    if(record.fields?.length){const dl=node("dl",null,"record-fields");record.fields.forEach(field=>dl.append(node("dt",field.label),node("dd",field.value)));article.append(dl);}
    if(record.summary)article.append(node("p",record.summary));
    if(record.kind!=="encounter"){
      const actions=node("div",null,"row");actions.append(actionButton("查看原件",()=>openOriginal(record.kind,record.id),true));
      if(record.kind==="clinical")actions.append(actionButton("查看审核记录",()=>{location.href=AppPaths.url(clinicalUrl(record));},true));
      article.append(actions);
    }
    section.append(article);
  });return section;
}
function unfiledModule(records) {
  const section=moduleShell("待整理与未归档资料",`${records.length} 份资料`,"unfiled-module");
  records.forEach(record=>{
    const article=node("article",null,"record-content");article.append(node("h3",record.original_name),node("p",`${stateNames[record.status]||record.status} · ${record.candidate_date?`识别/暂存日期：${record.candidate_date}（待确认）`:"就诊日期待识别或补填"}`,"muted"));
    const actions=node("div",null,"row");actions.append(actionButton("查看原件",()=>openOriginal(record.kind,record.id),true));if(!isStudent||record.kind==="clinical"||patientPermissions.includes("edit"))actions.append(actionButton(record.status==="rejected"?"查看审核记录":isStudent&&!patientPermissions.includes("edit")&&!patientPermissions.includes("review")?"查看资料":"识别并审核",()=>{location.href=AppPaths.url(clinicalUrl(record));},true));article.append(actions);section.append(article);
  });return section;
}
async function openOriginal(kind,id) {
  const paths={clinical:`/clinical-documents/${id}/file`,patient:`/patient-documents/${id}/file`,intake:`/intake-submissions/${id}/document`};
  const response=await AppPaths.fetch(paths[kind],{headers:{Authorization:`Bearer ${token}`}});
  if(!response.ok){if(response.status===401)AppSession.logout(staffRole,true);const error=await response.json().catch(()=>({}));throw new Error(error.detail||"原件暂时无法打开");}
  const url=URL.createObjectURL(await response.blob());window.open(url,"_blank","noopener");setTimeout(()=>URL.revokeObjectURL(url),60000);
}
async function createInvite() {
  const id=selectedPatientId;if(!id)return;$("showPatientQr").disabled=true;
  try {
    const data=await api(`/patients/${id}/intake-link`,{method:"POST"});if(id!==selectedPatientId)return;
    currentInvitationId=data.id;$("qr").innerHTML=data.qr_svg;$("qrPatientName").textContent=data.display_name;$("openInvite").href=data.intake_url;$("qrUrl").textContent=data.intake_url;
    const revoked=data.state!=="available";$("expiry").textContent=revoked?"此码已停用，患者无法继续使用。":"长期有效 · 可重复扫码 · 无需核验码";
    $("printInvite").disabled=revoked;$("revokeInvite").disabled=revoked;$("openInvite").classList.toggle("hidden",revoked);showModal("inviteCard");
  }catch(error){message(error.message,true);}finally{$("showPatientQr").disabled=!selectedPatientId;}
}
async function reviewIntake(submission,action) {
  await api(`/intake-submissions/${submission.id}/review`,{method:"POST",body:JSON.stringify({action})});await loadIntakes();await loadPatients();message(action==="approve"?"已批准，可在患者档案中查看":"申请已驳回");
}
async function loadIntakes() {
  try {
    const items=await api("/intake-submissions");$("intakes").replaceChildren(...items.map(submission=>{
      const item=node("article",null,"patient-card-wide");item.append(detailLine("患者姓名",submission.display_name),detailLine("基本信息",`${submission.sex} · ${submission.date_of_birth} · ${submission.operator_relationship}`),detailLine("状态",stateNames[submission.status]||submission.status),detailLine("资料",submission.has_document?"原件已保存，待识别核对":"仅提交基本信息，未上传病历"));
      const bar=node("div",null,"intake-action-bar");
      if(submission.has_document){const actions=node("div",null,"intake-document-actions");actions.append(actionButton("查看原始资料",()=>openOriginal("intake",submission.id),true));if(!isStudent||submission.permissions?.includes("edit"))actions.append(actionButton("识别并逐字段审核",()=>{location.href=AppPaths.url(`/clinical?source=intake&id=${submission.id}`);},true));bar.append(actions);}
      if(submission.status==="pending"&&(!isStudent||submission.permissions?.includes("review"))){const actions=node("div",null,"intake-review-actions");const reject=actionButton("驳回",()=>reviewIntake(submission,"reject"));reject.className="danger";actions.append(actionButton("批准",()=>reviewIntake(submission,"approve")),reject);bar.append(actions);}
      item.append(bar);return item;
    }));if(!items.length)$("intakes").append(node("p","暂无建档申请。请先在患者管理中录入姓名并生成专属建档码。","muted"));
  }catch(error){message(error.message,true);}
}
async function loadCurrentNotice() {const notice=await api("/doctor/patient-notices/current");$("doctorNoticeSummary").textContent=`${notice.title} · 版本 ${notice.version}`;$("doctorNoticeContent").textContent=notice.content;}
$("newPatientForm").onsubmit=async event=>{
  event.preventDefault();const button=event.target.querySelector('button[type="submit"]');button.disabled=true;
  try {const patient=await api("/patients",{method:"POST",body:JSON.stringify({display_name:$("patientName").value.trim()})});event.target.reset();closeModal("newPatientCard");await loadPatients(patient.id);message("患者已保存，可从档案顶部打开建档二维码。");}
  catch(error){$("newPatientError").textContent=error.message;$("newPatientError").classList.remove("hidden");}finally{button.disabled=false;}
};
$("showNewPatient").onclick=()=>{$("newPatientError").classList.add("hidden");showModal("newPatientCard");$("patientName").focus();};
$("cancelNewPatient").onclick=()=>closeModal("newPatientCard");
$("createIntakeLink").onclick=()=>{openNewPatientAfterView=true;if(location.hash==="#patients")activateDoctorView();else location.hash="patients";};
$("refreshIntakes").onclick=loadIntakes;$("patientSearch").oninput=renderPatients;
$("showPatientQr").onclick=createInvite;$("refreshPatient").onclick=()=>loadPatients().catch(error=>message(error.message,true));
$("printInvite").onclick=()=>window.print();$("closeInvite").onclick=()=>closeModal("inviteCard");
$("revokeInvite").onclick=async()=>{
  if(!currentInvitationId)return;$("revokeInvite").disabled=true;
  try {await api(`/intake-links/${currentInvitationId}/revoke`,{method:"POST"});$("expiry").textContent="此码已停用，已打印的二维码也无法继续使用。";$("printInvite").disabled=true;$("openInvite").classList.add("hidden");}
  catch(error){$("expiry").textContent=error.message;$("revokeInvite").disabled=false;}
};
["newPatientCard","inviteCard"].forEach(id=>{$(id).onclose=()=>$(id).classList.add("hidden");});
$("logout").onclick=()=>AppSession.logout(staffRole);window.addEventListener("hashchange",activateDoctorView);
window.addEventListener("pageshow",event=>{if(event.persisted&&token)loadPatients().catch(error=>message(error.message,true));});
async function init(){if(!token)return;try{const me=await api("/auth/me");if(me.role!==staffRole){AppSession.logout(staffRole);return;}doctorId=me.id;DoctorShell.setUser(me.display_name);if(isStudent){["showNewPatient","showPatientQr","createIntakeLink"].forEach(id=>$(id).classList.add("hidden"));}activateDoctorView();await Promise.all([loadPatients(),loadCurrentNotice()]);if(isStudent&&!doctorPatients.length){$("patientMeta").textContent="请联系所属医生设置访问权限。";$("patientDetailScroll").replaceChildren(emptyState("暂无访问权限","医生开启查看权限后，刷新即可查看其名下患者；权限到期或撤销后无法访问。"));}}catch(error){message(error.message,true);}}
init();
