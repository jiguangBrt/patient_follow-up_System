(() => {
  const $ = id => document.getElementById(id);
  const role = AppSession.staffRole(), token = AppSession.require(role);
  const dialogIds = ["studentDialog", "grantDialog", "recordsDialog"];
  let students = [], patients = [], grants = [], recordsStudentId = null;
  let creatingStudent = false, creatingGrant = false;
  const format = new Intl.DateTimeFormat("zh-CN", {timeZone:"Asia/Shanghai",dateStyle:"short",timeStyle:"short",hour12:false});
  const time = value => value ? format.format(new Date(value)) : "暂无记录";
  const localTime = date => new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
  const node = (tag,text) => {const el=document.createElement(tag);if(text!=null)el.textContent=text;return el;};
  function message(text,error=false) {$("message").textContent=text;$("message").className=`status ${error?"error":"success"}`;}
  function dialogError(id,text="") {$(id).textContent=text;$(id).classList.toggle("hidden",!text);}
  function closeModal(id) {if($(id).open)$(id).close();}
  function openModal(id) {dialogIds.filter(other=>other!==id).forEach(closeModal);if(!$(id).open)$(id).showModal();}
  async function api(path, options={}) {
    const response=await AppPaths.fetch(path,{...options,headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`}});
    const data=await response.json();
    if(!response.ok){if(response.status===401)AppSession.logout(role,true);throw new Error(typeof data.detail==="string"?data.detail:"请检查输入信息和时间范围。");}
    return data;
  }
  function action(text,callback,errorId=null) {
    const button=node("button",text);button.type="button";button.className="secondary";
    button.onclick=async()=>{button.disabled=true;try{await callback();}catch(error){errorId?dialogError(errorId,error.message):message(error.message,true);}finally{button.disabled=false;}};
    return button;
  }
  function row(values) {
    const tr=node("tr");values.forEach(value=>{const td=node("td");if(typeof value==="string")td.textContent=value;else td.append(value);tr.append(td);});return tr;
  }
  function empty(body,count,text) {if(!body.children.length){const td=node("td",text);td.colSpan=count;td.className="team-empty";const tr=node("tr");tr.append(td);body.append(tr);}}
  function resetStudent() {
    $("studentForm").reset();$("studentConfirm").setCustomValidity("");dialogError("studentError");
    [["studentPassword","showPassword"],["studentConfirm","showConfirm"]].forEach(([input,id])=>{$(input).type="password";$(id).textContent="显示密码";$(id).setAttribute("aria-pressed","false");});
  }
  function openStudent() {if(creatingStudent)return;resetStudent();openModal("studentDialog");$("studentUsername").focus();}
  function openGrant(student) {
    if(creatingGrant||!student.is_active)return;
    $("grantForm").reset();dialogError("grantError");$("grantStudent").value=String(student.id);
    $("grantStudentName").textContent=`${student.display_name} · ${student.username}`;
    $("grantPatient").replaceChildren(new Option(patients.length?"请选择患者":"暂无患者，请先在患者管理中建档",""),...patients.map(p=>new Option(`${p.display_name}（${p.patient_code}）`,String(p.id))));
    $("grantStart").value=localTime(new Date());$("grantEnd").value=localTime(new Date(Date.now()+30*86400000));
    $("createGrantButton").disabled=!patients.length;openModal("grantDialog");$("grantPatient").focus();
  }
  function renderRecords() {
    const student=students.find(s=>s.id===recordsStudentId);if(!student)return;
    $("recordsDialogTitle").textContent=`${student.display_name}的授权记录`;$("grantFromRecords").disabled=!student.is_active;
    const states={active:"有效",scheduled:"尚未生效",expired:"已到期",revoked:"已撤销"};
    $("grants").replaceChildren(...grants.filter(g=>g.student_id===recordsStudentId).map(g=>{
      const patient=patients.find(p=>p.id===g.patient_id);
      const operations=["查看",...(g.can_edit?["录入"]:[]),...(g.can_review?["审核"]:[])].join("、");
      const status=states[g.state]+(g.revoked_at?`\n${time(g.revoked_at)} · 撤销人 #${g.revoked_by_id}`:"");
      return row([patient?.display_name||`患者 #${g.patient_id}`,`${operations}\n用途：${g.purpose}`,`${time(g.starts_at)}\n至 ${time(g.ends_at)}`,status,g.state==="active"||g.state==="scheduled"?action("撤销授权",async()=>{dialogError("recordsError");await api(`/doctor/patient-grants/${g.id}/revoke`,{method:"POST"});await load();message("授权已撤销。其他有效授权需分别撤销。");},"recordsError"):"—"]);
    }));
    empty($("grants"),5,"暂无授权记录，可点击右下角“分配权限”。");
  }
  async function openRecords(student) {recordsStudentId=student.id;dialogError("recordsError");renderRecords();openModal("recordsDialog");await load();}
  async function load() {
    [students,patients,grants]=await Promise.all([api("/doctor/students"),api("/patients"),api("/doctor/patient-grants")]);
    $("studentCount").textContent=`${students.length} 人`;
    $("students").replaceChildren(...students.map(student=>{
      const operations=node("div");operations.className="team-actions";
      const assign=action("分配权限",()=>openGrant(student));assign.disabled=!student.is_active;assign.setAttribute("aria-haspopup","dialog");
      const records=action("授权记录",()=>openRecords(student),"recordsError");records.setAttribute("aria-haspopup","dialog");
      const toggle=action(student.is_active?"停用":"启用",async()=>{await api(`/doctor/students/${student.id}`,{method:"PATCH",body:JSON.stringify({is_active:!student.is_active})});await load();message("学生账号状态已更新。");});
      if(student.is_active)toggle.classList.add("stop-student");operations.append(assign,records,toggle);
      const state=node("span",student.is_active?"启用":"停用");state.className=`account-state ${student.is_active?"":"inactive"}`;
      const count=new Set(grants.filter(g=>g.student_id===student.id&&g.state==="active").map(g=>g.patient_id)).size;
      return row([student.display_name,student.username,state,`${count} 位`,time(student.last_login_at),operations]);
    }));
    empty($("students"),6,"暂无学生，点击右上角“新增学生”开通账号。");
    if($("recordsDialog").open)renderRecords();
  }
  [["studentPassword","showPassword"],["studentConfirm","showConfirm"]].forEach(([input,id])=>{
    $(id).onclick=()=>{const visible=$(input).type==="password";$(input).type=visible?"text":"password";$(id).textContent=visible?"隐藏密码":"显示密码";$(id).setAttribute("aria-pressed",String(visible));};
    $(input).oninput=()=>$("studentConfirm").setCustomValidity("");
  });
  $("studentForm").onsubmit=async event=>{
    event.preventDefault();if(creatingStudent)return;dialogError("studentError");
    if($("studentPassword").value!==$("studentConfirm").value){$("studentConfirm").setCustomValidity("两次输入的密码不一致。");$("studentConfirm").reportValidity();return;}
    creatingStudent=true;$("createStudentButton").disabled=true;$("newStudent").disabled=true;
    try {
      await api("/doctor/students",{method:"POST",body:JSON.stringify({username:$("studentUsername").value,display_name:$("studentName").value,password:$("studentPassword").value})});
      closeModal("studentDialog");resetStudent();message("学生账号已开通，可在列表中点击“分配权限”。");await load();
    } catch(error) {$("studentDialog").open?dialogError("studentError",error.message):message(error.message,true);}
    finally {creatingStudent=false;$("createStudentButton").disabled=false;$("newStudent").disabled=false;}
  };
  $("grantForm").onsubmit=async event=>{
    event.preventDefault();if(creatingGrant)return;dialogError("grantError");creatingGrant=true;$("createGrantButton").disabled=true;
    try {
      const start=new Date($("grantStart").value),end=new Date($("grantEnd").value);
      if(!Number.isFinite(start.getTime())||!Number.isFinite(end.getTime())||end<=start||end<=new Date())throw new Error("结束时间必须晚于当前时间和开始时间。");
      await api("/doctor/patient-grants",{method:"POST",body:JSON.stringify({student_id:Number($("grantStudent").value),patient_id:Number($("grantPatient").value),purpose:$("grantPurpose").value,can_edit:$("grantEdit").checked,can_review:$("grantReview").checked,starts_at:start.toISOString(),ends_at:end.toISOString()})});
      closeModal("grantDialog");message("患者权限已授予。");await load();
    } catch(error) {$("grantDialog").open?dialogError("grantError",error.message):message(error.message,true);}
    finally {creatingGrant=false;$("createGrantButton").disabled=!patients.length;}
  };
  document.querySelectorAll("[data-close]").forEach(button=>{button.onclick=()=>closeModal(button.dataset.close);});
  $("studentDialog").onclose=resetStudent;
  $("newStudent").onclick=openStudent;
  $("grantFromRecords").onclick=()=>{const student=students.find(s=>s.id===recordsStudentId);if(student)openGrant(student);};
  $("refreshTeam").onclick=()=>load().catch(error=>message(error.message,true));
  $("logout").onclick=()=>AppSession.logout(role);
  async function init() {
    if(!token)return;
    try {const me=await api("/auth/me");if(me.role!=="doctor")throw new Error("只有医生可以开通学生账号和分配权限。");DoctorShell.setUser(me.display_name);await load();$("teamContent").classList.remove("hidden");}
    catch(error) {message(error.message,true);}
  }
  init();
})();
