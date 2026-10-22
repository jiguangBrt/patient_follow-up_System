const $ = id => document.getElementById(id);
const intakeToken = new URLSearchParams(location.hash.slice(1)).get("token") || AppPaths.storage.getItem("intakeToken");
let currentNotice = null;
let previewUrl = null;
let submitting = false;
const keyName = `intakeSubmissionKey:${intakeToken}`;
function newKey() { const bytes = new Uint8Array(24); crypto.getRandomValues(bytes); const key = Array.from(bytes,b=>b.toString(16).padStart(2,"0")).join(""); AppPaths.storage.setItem(keyName,key); return key; }
let submissionKey = AppPaths.storage.getItem(keyName) || newKey();
if (intakeToken) { AppPaths.storage.setItem("intakeToken",intakeToken); history.replaceState(null,"",location.pathname); }
function status(text,error=false) { $("status").textContent=text; $("status").className=`status ${error?"error":"success"}`; }
async function request(path,body) {
  const response=await AppPaths.fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok) { const error=new Error(typeof data.detail==="string"?data.detail:"请检查填写的信息和文件。"); error.status=response.status; throw error; }
  return data;
}
function showReviewStatus(reviewStatus, submittedAt, hasDocument, noticeVersion = null) {
  const approved = reviewStatus === "approved";
  $("noticeStep").classList.add("hidden");$("intakeForm").classList.add("hidden");$("done").classList.remove("hidden");
  $("stepLabel").textContent=approved?"审核已通过":"已提交";
  $("pageTitle").textContent=approved?"建档已通过":"等待医生审核";
  $("completionTitle").textContent=approved?"医生已通过审核":"信息已提交";
  $("completionDescription").textContent=approved?"无需重复建档。如需补交病历，可点击下方按钮。":"信息已提交，等待医生审核，请勿重复提交。审核通过后可以再次扫码补交病历。";
  $("consentReceipt").textContent=submittedAt?`${noticeVersion?`患者须知 ${noticeVersion} · `:""}提交时间：${new Date(submittedAt).toLocaleString()}。${hasDocument?"已附病历文件。":"此次仅提交基本信息，未上传病历文件。"}`:"";
  $("submitMore").classList.toggle("hidden",!approved);
  status(approved?"审核已通过，无需重复提交基本信息。":"信息已提交，等待医生审核。");
}
async function check(allowSupplement = false) {
  if(!intakeToken) {status("二维码不可用，请联系医护人员",true);return;}
  try {
    const data=await request("/intake-links/status",{intake_token:intakeToken});
    if(data.state!=="available") throw new Error("二维码已停用或失效，请联系医护人员。");
    $("displayName").readOnly=Boolean(data.locked_name);
    $("displayName").value=data.locked_name||"";
    if(data.locked_name) status(`${data.locked_name}的专属建档页，姓名由医生设定。`);
    else status("请先阅读当前患者须知。");
    if(data.profile) {$("sex").value=data.profile.sex;$("dateOfBirth").value=data.profile.date_of_birth;$("relationship").value=data.profile.operator_relationship;status("基本信息已保存，可核对后补交病历。");}
    if(data.submission_status==="pending" || (data.submission_status==="approved" && !allowSupplement)) {
      showReviewStatus(data.submission_status,data.submitted_at,data.profile?.has_document);return;
    }
    $("done").classList.add("hidden");$("intakeForm").classList.add("hidden");
    $("document").required=data.submission_status==="approved";
    $("documentLabel").textContent=data.submission_status==="approved"?"补交纸质病历或报告（必选）":"纸质病历或报告（选填）";
    $("formHelp").textContent=data.submission_status==="approved"?"建档已经通过，请选择要补交的病历文件，无需重复申请建档。":"请填写基本信息。病历可选填，提交后请等待医生审核。";
    $("submitButton").textContent=data.submission_status==="approved"?"提交补交病历":"提交给医生审核";
    $("stepLabel").textContent="第 1 步，共 2 步";$("pageTitle").textContent="阅读患者须知";
    if(data.submission_status==="rejected") {submissionKey=newKey();status(`上次申请已驳回，请核对后重新提交。${data.review_note||""}`,true);}
    const response=await AppPaths.fetch("/patient-notices/current",{cache:"no-store"});currentNotice=await response.json();
    if(!response.ok) throw new Error("患者须知暂不可用，请稍后再试。");
    $("noticeTitle").textContent=currentNotice.title;$("noticeVersion").textContent=`版本 ${currentNotice.version}`;
    $("noticeContent").replaceChildren(...currentNotice.content.split("\n").filter(Boolean).map(text=>{const p=document.createElement("p");p.textContent=text;return p;}));
    $("noticeStep").classList.remove("hidden");
  } catch(error) {status(error.message,true);$("noticeStep").classList.add("hidden");$("intakeForm").classList.add("hidden");$("done").classList.add("hidden");}
}
$("intakeForm").onsubmit=async event=>{
  event.preventDefault();if(submitting)return;submitting=true;$("submitButton").disabled=true;
  try {
    const body={intake_token:intakeToken,submission_key:submissionKey,display_name:$("displayName").value.trim(),sex:$("sex").value,date_of_birth:$("dateOfBirth").value,operator_relationship:$("relationship").value,notice_version_id:currentNotice.id,consent_given:$("consent").checked};
    const file=$("document").files[0];
    if(file){
      if(file.size>8*1024*1024) throw new Error("资料不能超过 8 MB，也可以先不上传。");
      const bytes=new Uint8Array(await file.arrayBuffer());let binary="";bytes.forEach(byte=>{binary+=String.fromCharCode(byte);});
      Object.assign(body,{document_name:file.name,document_mime_type:file.type,document_base64:btoa(binary)});
    }
    const result=await request("/intake-submissions",body);
    showReviewStatus(result.status,result.created_at,result.has_document,result.notice_version);
    $("document").value="";$("preview").classList.add("hidden");
  } catch(error) {if(error.status===409){$("consent").checked=false;$("continueButton").disabled=true;await check();}else{status(error.message||"提交失败，请稍后再试。",true);if(error.status===410){$("intakeForm").classList.add("hidden");status("二维码已停用，无法继续提交，请联系医护人员。",true);}}}
  finally {submitting=false;$("submitButton").disabled=false;}
};
$("consent").onchange=()=>{$("continueButton").disabled=!$("consent").checked;};
$("continueButton").onclick=()=>{$("noticeStep").classList.add("hidden");$("intakeForm").classList.remove("hidden");$("stepLabel").textContent="第 2 步，共 2 步";$("pageTitle").textContent=$("document").required?"补交病历":"填写基本信息";window.scrollTo({top:0,behavior:"smooth"});};
$("submitMore").onclick=()=>{submissionKey=newKey();$("consent").checked=false;$("continueButton").disabled=true;$("submitButton").disabled=false;check(true);};
$("document").onchange=()=>{if(previewUrl)URL.revokeObjectURL(previewUrl);const file=$("document").files[0];if(file&&file.type.startsWith("image/")){previewUrl=URL.createObjectURL(file);$("preview").src=previewUrl;$("preview").classList.remove("hidden");}else $("preview").classList.add("hidden");};
check();
