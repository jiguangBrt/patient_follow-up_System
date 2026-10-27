(() => {
  const $ = id => document.getElementById(id);
  const role = AppSession.staffRole(), token = AppSession.require(role);
  let students = [], patients = [], grants = [];
  const format = new Intl.DateTimeFormat("zh-CN", {timeZone:"Asia/Shanghai",dateStyle:"short",timeStyle:"short",hour12:false});
  const time = value => value ? format.format(new Date(value)) : "暂无记录";
  const localTime = date => new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
  const node = (tag,text) => {const el=document.createElement(tag);if(text!=null)el.textContent=text;return el;};
  function message(text,error=false){$("message").textContent=text;$("message").className=`status ${error?"error":"success"}`;}
  async function api(path, options={}){
    const response=await AppPaths.fetch(path,{...options,headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`}});
    const data=await response.json();if(!response.ok){if(response.status===401)AppSession.logout(role,true);throw new Error(typeof data.detail==="string"?data.detail:"请检查输入信息和时间范围。");}return data;
  }
  function action(text,callback){const button=node("button",text);button.type="button";button.className="secondary";button.onclick=async()=>{button.disabled=true;try{await callback();}catch(error){message(error.message,true);}finally{button.disabled=false;}};return button;}
  function row(values){const tr=node("tr");values.forEach(value=>{const td=node("td");if(typeof value==="string")td.textContent=value;else td.append(value);tr.append(td);});return tr;}
  function empty(body, count){if(!body.children.length){const td=node("td","暂无记录");td.colSpan=count;const tr=node("tr");tr.append(td);body.append(tr);}}
  async function load(){
    [students,patients,grants]=await Promise.all([api("/doctor/students"),api("/patients"),api("/doctor/patient-grants")]);
    $("students").replaceChildren(...students.map(s=>row([s.display_name,s.username,s.is_active?"启用":"停用",time(s.last_login_at),action(s.is_active?"停用":"启用",async()=>{await api(`/doctor/students/${s.id}`,{method:"PATCH",body:JSON.stringify({is_active:!s.is_active})});await load();message("学生账号状态已更新。");})])));empty($("students"),5);
    const studentChoice=$("grantStudent").value, patientChoice=$("grantPatient").value;
    $("grantStudent").replaceChildren(new Option("请选择学生",""),...students.filter(s=>s.is_active).map(s=>new Option(`${s.display_name}（${s.username}）`,String(s.id))));
    $("grantPatient").replaceChildren(new Option("请选择患者",""),...patients.map(p=>new Option(`${p.display_name}（${p.patient_code}）`,String(p.id))));
    $("grantStudent").value=studentChoice;$("grantPatient").value=patientChoice;
    const states={active:"有效",scheduled:"尚未生效",expired:"已到期",revoked:"已撤销"};
    $("grants").replaceChildren(...grants.map(g=>{
      const student=students.find(s=>s.id===g.student_id), patient=patients.find(p=>p.id===g.patient_id);
      const operations=["查看",...(g.can_edit?["录入"]:[]),...(g.can_review?["审核"]:[])].join("、");
      const status=states[g.state]+(g.revoked_at?`\n${time(g.revoked_at)} · 撤销人 #${g.revoked_by_id}`:"");
      return row([`${student?.display_name||"学生 #"+g.student_id} / ${patient?.display_name||"患者 #"+g.patient_id}`,`${operations}\n用途：${g.purpose}`,`${time(g.starts_at)} 至 ${time(g.ends_at)}`,status,g.state==="active"||g.state==="scheduled"?action("撤销授权",async()=>{await api(`/doctor/patient-grants/${g.id}/revoke`,{method:"POST"});await load();message("授权已撤销；其他仍有效的授权需分别撤销。");}):"—"]);
    }));empty($("grants"),5);
  }
  function defaults(){$("grantStart").value=localTime(new Date());$("grantEnd").value=localTime(new Date(Date.now()+30*86400000));}
  [["studentPassword","showPassword"],["studentConfirm","showConfirm"]].forEach(([input,id])=>{$(id).onclick=()=>{const visible=$(input).type==="password";$(input).type=visible?"text":"password";$(id).textContent=visible?"隐藏密码":"显示密码";$(id).setAttribute("aria-pressed",String(visible));};$(input).oninput=()=>$("studentConfirm").setCustomValidity("");});
  $("studentForm").onsubmit=async event=>{
    event.preventDefault();if($("studentPassword").value!==$("studentConfirm").value){$("studentConfirm").setCustomValidity("两次输入的密码不一致。");$("studentConfirm").reportValidity();return;}
    const button=event.target.querySelector('button[type="submit"]');button.disabled=true;
    try{await api("/doctor/students",{method:"POST",body:JSON.stringify({username:$("studentUsername").value,display_name:$("studentName").value,password:$("studentPassword").value})});event.target.reset();[["studentPassword","showPassword"],["studentConfirm","showConfirm"]].forEach(([input,id])=>{$(input).type="password";$(id).textContent="显示密码";$(id).setAttribute("aria-pressed","false");});await load();message("学生账号已开通，请继续分配患者权限。");}catch(error){message(error.message,true);}finally{button.disabled=false;}
  };
  $("grantForm").onsubmit=async event=>{
    event.preventDefault();const button=event.target.querySelector('button[type="submit"]');button.disabled=true;
    try{const start=new Date($("grantStart").value),end=new Date($("grantEnd").value);if(end<=start||end<=new Date())throw new Error("结束时间必须晚于当前时间和开始时间。");await api("/doctor/patient-grants",{method:"POST",body:JSON.stringify({student_id:Number($("grantStudent").value),patient_id:Number($("grantPatient").value),purpose:$("grantPurpose").value,can_edit:$("grantEdit").checked,can_review:$("grantReview").checked,starts_at:start.toISOString(),ends_at:end.toISOString()})});await load();message("患者权限已授予。");}catch(error){message(error.message,true);}finally{button.disabled=false;}
  };
  $("refreshTeam").onclick=()=>load().catch(error=>message(error.message,true));$("logout").onclick=()=>AppSession.logout(role);
  async function init(){if(!token)return;try{const me=await api("/auth/me");if(me.role!=="doctor")throw new Error("只有医生可以开通学生账号和分配权限。");DoctorShell.setUser(me.display_name);await load();defaults();$("teamContent").classList.remove("hidden");message("仅显示你自己的学生和授权记录。");}catch(error){message(error.message,true);}}
  init();
})();
