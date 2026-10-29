const $ = id => document.getElementById(id);
let currentNotice=null, entry=null, accessToken=null, profile=null, formController=null, previewUrl=null;
let storageWarning=false, operation=false, viewSequence=0, uploadKey=null, recoveryRequired=false;
const memoryStore=new Map();
const entryStorageKey=`patient-portal:${AppPaths.url("/")}:entry`;
function readEntryToken(){try{return AppPaths.storage.getItem("intakeToken");}catch{return null;}}
const intakeToken=new URLSearchParams(location.hash.slice(1)).get("token") || readEntryToken() || storageGet(entryStorageKey);
if(intakeToken){try{AppPaths.storage.setItem("intakeToken",intakeToken);}catch{storageWarning=true;}storageSet(entryStorageKey,intakeToken);history.replaceState(null,"",location.pathname);}
const today=()=>new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,10);
const privateKey=()=>`patient-portal:${AppPaths.url("/")}:doctor:${entry.doctor_id}`;
function storageGet(key){try{return localStorage.getItem(key)||memoryStore.get(key);}catch{storageWarning=true;return memoryStore.get(key);}}
function storageSet(key,value){memoryStore.set(key,value);try{localStorage.setItem(key,value);}catch{storageWarning=true;}}
function storageRemove(key){memoryStore.delete(key);try{localStorage.removeItem(key);}catch{storageWarning=true;}}
function randomKey(){return Array.from(crypto.getRandomValues(new Uint8Array(24)),b=>b.toString(16).padStart(2,"0")).join("");}
function status(text,error=false){$("status").textContent=text;$("status").className=`status ${error?"error":"success"}`;if(error)window.scrollTo({top:0});}
async function request(path,body,method="POST",authenticated=true) {
  const headers={"Content-Type":"application/json"};if(authenticated&&accessToken)headers.Authorization=`Bearer ${accessToken}`;
  const response=await AppPaths.fetch(path,{method,headers,cache:"no-store",...(body===undefined?{}:{body:JSON.stringify(body)})});
  const data=await readResponse(response);
  if(!response.ok){const error=new Error(typeof data.detail==="string"?data.detail:"请检查填写的信息和文件。");error.status=response.status;throw error;}
  return data;
}
async function readResponse(response) {
  try{return JSON.parse(await response.text());}
  catch {const error=new Error(response.status===413?"上传请求过大，请选择不超过 8 MB 的 JPG、PNG 或 PDF 文件。":response.status>=500?"服务器暂时无法接收请求，请稍后重试；若持续失败，请联系管理员。":"服务器返回了异常内容，请刷新页面后重试。");error.status=response.status;throw error;}
}
// End response helpers.
async function notice(){
  const value=await request("/patient-notices/current",undefined,"GET",false);currentNotice=value;
  $("noticeTitle").textContent=value.title;$("noticeVersion").textContent=`版本 ${value.version}`;
  $("noticeContent").replaceChildren(...value.content.split("\n").map(text=>{const p=document.createElement("p");p.textContent=text;return p;}));return value;
}
function setProfile(data){
  profile=data.profile||{};const patient=data.patient||{};
  $("displayName").value=entry.locked_name||profile.display_name||patient.display_name||"";$("displayName").readOnly=Boolean(entry.locked_name);$("sex").value=profile.sex||"未说明";
  $("dateOfBirth").value=profile.date_of_birth||"";$("phone").value=profile.phone||"";$("relationship").value=profile.operator_relationship||"本人";
  $("welcomeName").textContent=`${patient.display_name||profile.display_name||"您"}，您好`;
  $("profileHelp").textContent="";$("saveProfile").textContent="保存基本信息";
  $("registerConsentRow").classList.add("hidden");$("registerConsent").required=false;$("deviceSection").classList.remove("hidden");
}
async function go(name){
  if(operation)return;
  if(!accessToken||recoveryRequired)name="me";
  const sequence=++viewSequence;
  document.querySelectorAll(".portal-view").forEach(el=>el.classList.toggle("hidden",el.id!==`${name}View`));
  document.querySelectorAll(".portal-bottom button").forEach(el=>{if(el.dataset.go===(name==="me"?"me":"home"))el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");});
  $("pageTitle").textContent=({home:"首页",me:"我的",health:"健康档案",records:"诊疗记录",upload:"添加记录"})[name];
  window.scrollTo({top:0});
  try{
    if(name==="health")await loadHealth(sequence);
    if(name==="records")await loadDocuments(sequence);
    if(name==="upload"){$("eventDate").value||=today();uploadKey||=randomKey();}
  }catch(error){status(error.message,true);}
}
async function loadHealth(sequence){
  $("healthHistory").textContent="正在读取…";
  const data=await request("/portal/gastritis-records",undefined,"GET");if(sequence!==viewSequence)return;
  const records=data.records||[];const payload=structuredClone(records[0]?.payload||{});
  if(!records.length)payload.basic={name:$("displayName").value,sex:profile?.sex||"未说明",date_of_birth:profile?.date_of_birth||"",phone:profile?.phone||"",...(payload.basic||{})};
  formController=await GastritisForms.render($("healthFields"),payload,{patient:true});
  if(sequence!==viewSequence)return;
  $("healthDate").value=today();$("healthHistory").replaceChildren();
  if(!records.length)$("healthHistory").textContent="暂无记录，填写后保存即可。";
  records.forEach(record=>{
    const row=document.createElement("div");row.className="portal-card";const title=document.createElement("p");
    title.textContent=`${record.recorded_on} · 第 ${record.version} 版 · ${record.status==="confirmed"?"医生已核对":record.source==="patient"?"患者自述 / 待核对":"医生草稿 / 待核对"}`;
    const button=document.createElement("button");button.type="button";button.className="secondary";button.textContent="查看本次记录";
    button.onclick=async()=>{try{await GastritisForms.render($("recordDetail"),record.payload,{patient:true,readonly:true});$("recordDetail").querySelectorAll("input,select,textarea,button").forEach(el=>el.disabled=true);$("recordDialog").showModal();}catch(error){status(error.message,true);}};
    row.append(title,button);$("healthHistory").append(row);
  });
}
async function loadDocuments(sequence){
  $("documentList").textContent="正在读取…";const records=await request("/portal/documents",undefined,"GET");if(sequence!==viewSequence)return;
  $("documentList").replaceChildren();if(!records.length){$("documentList").textContent="暂无诊疗记录，点击“添加记录”上传病历或报告。";return;}
  [...records].sort((a,b)=>b.event_date.localeCompare(a.event_date)||b.id-a.id).forEach(record=>{
    const card=document.createElement("article");card.className="portal-card";
    const date=document.createElement("p");date.className="portal-record-meta";date.textContent=record.event_date;
    const title=document.createElement("h3");title.textContent=record.display_label;
    const file=document.createElement("p");file.className="portal-record-name";file.textContent=record.original_name;
    const state=document.createElement("p");state.textContent=({pending:"资料已保存，待医生整理",approved:"医生已核对",rejected:"请核对后补充资料"})[record.review_status]||"资料已保存";
    const open=document.createElement("button");open.type="button";open.className="secondary";open.textContent="查看原件";open.onclick=()=>openFile(record,open);
    card.append(date,title,file,state,open);$("documentList").append(card);
  });
}
async function openFile(record,button){
  button.disabled=true;let objectUrl;
  try{const response=await AppPaths.fetch(`/portal/documents/${record.id}/file`,{headers:{Authorization:`Bearer ${accessToken}`},cache:"no-store"});if(!response.ok)throw new Error("原件暂时无法打开，请稍后重试。");objectUrl=URL.createObjectURL(await response.blob());const a=document.createElement("a");a.href=objectUrl;a.download=record.original_name;a.click();setTimeout(()=>URL.revokeObjectURL(objectUrl),60000);}catch(error){if(objectUrl)URL.revokeObjectURL(objectUrl);status(error.message,true);}finally{button.disabled=false;}
}
async function busy(button,action){
  if(operation)return;operation=true;button.disabled=true;
  try{await action();}catch(error){status(error.message||"保存失败，请稍后重试。",true);if(error.status===409){try{await notice();$("uploadConsent").checked=false;$("registerConsent").checked=false;}catch{}}}
  finally{operation=false;button.disabled=false;}
}
$("profileForm").onsubmit=async event=>{
  event.preventDefault();let success=false;
  await busy($("saveProfile"),async()=>{
    if(recoveryRequired)throw new Error("请联系医生核实身份并获取个人恢复二维码，避免重复建档。");
    const body={display_name:entry.locked_name||$("displayName").value.trim(),sex:$("sex").value,date_of_birth:$("dateOfBirth").value,phone:$("phone").value.trim()||null,operator_relationship:$("relationship").value};
    let data;
    if(accessToken)data=await request("/portal/me",body,"PUT");
    else{
      if(!$("registerConsent").checked)throw new Error("请先阅读并同意患者须知。");
      const registrationKey=storageGet(`${privateKey()}:registration`)||randomKey();storageSet(`${privateKey()}:registration`,registrationKey);
      data=await request("/portal/register",{...body,intake_token:intakeToken,registration_key:registrationKey,notice_version_id:currentNotice.id,consent_given:true},"POST",false);
      accessToken=data.access_token;storageSet(privateKey(),accessToken);storageRemove(`${privateKey()}:recovery`);recoveryRequired=false;
    }
    setProfile(data);status(storageWarning?"已保存。本浏览器限制本机存储，请保持本页面打开；关闭后可能需要联系医生恢复访问。":"");success=true;
  });if(success)await go("home");
};
$("healthForm").onsubmit=async event=>{event.preventDefault();let success=false;await busy($("saveHealth"),async()=>{
  if(!formController)throw new Error("健康档案尚未加载，请稍后重试。");
  await request("/portal/gastritis-records",{recorded_on:$("healthDate").value,payload:formController.read()});status("已保存");success=true;
});if(success)await go("health");};
$("uploadForm").onsubmit=async event=>{event.preventDefault();let success=false;await busy($("uploadButton"),async()=>{
  if(!$("uploadConsent").checked)throw new Error("请先阅读并同意患者须知。");const file=$("document").files[0];
  if(!file)throw new Error("请选择要上传的照片或文件。");if(file.size>8*1024*1024)throw new Error("资料不能超过 8 MB。");
  if(!["image/jpeg","image/png","application/pdf"].includes(file.type))throw new Error("请选择 JPG、PNG 或 PDF 文件。");
  const bytes=new Uint8Array(await file.arrayBuffer());let binary="";for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  await request("/portal/documents",{event_date:$("eventDate").value,display_label:$("recordType").value,patient_note:$("patientNote").value.trim()||null,submission_key:uploadKey,notice_version_id:currentNotice.id,consent_given:true,document_name:file.name,document_mime_type:file.type,document_base64:btoa(binary)});
  $("uploadForm").reset();clearPreview();uploadKey=null;status("上传成功");success=true;
});if(success)await go("records");};
function clearPreview(){if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null;$("preview").classList.add("hidden");$("preview").removeAttribute("src");}
$("document").onchange=()=>{clearPreview();uploadKey=randomKey();const file=$("document").files[0];$("fileName").textContent=file?`${file.name} · ${(file.size/1024/1024).toFixed(1)} MB`:"支持 JPG、PNG、PDF，每份不超过 8 MB。";if(file&&file.type.startsWith("image/")){previewUrl=URL.createObjectURL(file);$("preview").src=previewUrl;$("preview").classList.remove("hidden");}};
$("logoutPortal").onclick=async()=>{await busy($("logoutPortal"),async()=>{await request("/portal/logout",{});storageRemove(privateKey());storageRemove(`${privateKey()}:registration`);storageRemove(`${privateKey()}:recovery`);accessToken=null;location.reload();});};
document.querySelectorAll("[data-go]").forEach(button=>button.onclick=()=>go(button.dataset.go));
document.querySelectorAll("[data-notice]").forEach(button=>button.onclick=()=>$("noticeDialog").showModal());
$("closeNotice").onclick=()=>$("noticeDialog").close();$("closeRecord").onclick=()=>$("recordDialog").close();
async function init(){
  try{
    if(!intakeToken)throw new Error("请扫描医生提供的建档二维码进入。");
    entry=await request("/portal/entry",{intake_token:intakeToken},"POST",false);
    $("displayName").value=entry.locked_name||"";
    $("displayName").readOnly=Boolean(entry.locked_name);
    await notice();accessToken=storageGet(privateKey());
    if(accessToken){try{const me=await request("/portal/me",undefined,"GET");
      if(entry.kind==="patient" && entry.target_binding!==me.target_binding){recoveryRequired=true;$("profileForm").classList.add("hidden");$("deviceSection").classList.remove("hidden");$("profileHelp").textContent="此二维码与本机已保存的档案不同。请先退出本机访问，再确认使用的是本人二维码。";status("二维码与本机档案不同，未打开任何患者资料。",true);await go("me");return;}
      setProfile(me);status("");await go("home");return;}catch(error){if(![401,403,404,410].includes(error.status))throw error;storageRemove(privateKey());storageRemove(`${privateKey()}:registration`);storageSet(`${privateKey()}:recovery`,"required");accessToken=null;}}
    const needsRecovery=Boolean(storageGet(`${privateKey()}:recovery`));
    if(needsRecovery && entry.kind!=="patient"){
      recoveryRequired=true;$("profileForm").classList.add("hidden");$("profileHelp").textContent="本机访问已失效，请联系医生核实身份并获取个人恢复二维码，避免重复建档。";
      status("本机访问已失效，请联系医生获取个人恢复二维码。",true);
    }else{
      recoveryRequired=false;$("profileForm").classList.remove("hidden");
      if(entry.kind==="patient"){$("profileHelp").textContent="";$("saveProfile").textContent="保存并进入档案";}
      status(needsRecovery?"请核对本人信息，使用此个人二维码恢复访问。":"请先完善基本信息。");
    }
    await go("me");
  }catch(error){status(error.message,true);}
}
window.addEventListener("hashchange",()=>{const next=new URLSearchParams(location.hash.slice(1)).get("token");if(next&&next!==intakeToken)location.reload();});
init();
