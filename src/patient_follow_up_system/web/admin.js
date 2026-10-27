(() => {
  const $ = id => document.getElementById(id);
  const token = AppSession.require("admin");
  let accounts = [];
  const loginTimeFormat = new Intl.DateTimeFormat("zh-CN", {timeZone:"Asia/Shanghai", year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit", second:"2-digit", hour12:false});
  function message(text, error=false) { $("message").textContent=text; $("message").className=`status ${error?"error":"success"}`; }
  async function api(path, options={}) {
    const response=await AppPaths.fetch(path,{...options,headers:{"Content-Type":"application/json",Authorization:`Bearer ${token}`}});
    const data=await response.json();
    if(!response.ok) { if(response.status===401||response.status===403) AppSession.logout("admin",true); throw new Error(typeof data.detail==="string"?data.detail:"请检查输入内容。"); }
    return data;
  }
  function renderAccounts() {
    const query=$("accountSearch").value.trim().toLowerCase(), role=$("roleFilter").value, status=$("statusFilter").value;
    const filtered=accounts.filter(a=>(`${a.username} ${a.display_name}`.toLowerCase().includes(query))&&(!role||a.role===role)&&(!status||(status==="active")===a.is_active));
    $("accountCounts").textContent=`共 ${accounts.length} 个账号 · 当前显示 ${filtered.length} 个`;
    $("accounts").replaceChildren(...filtered.map(account=>{
      const row=document.createElement("tr");
      [account.display_name,account.username,({doctor:"医生",student:"学生",patient:"患者"})[account.role],account.mentor_doctor_id?(accounts.find(a=>a.id===account.mentor_doctor_id)?.display_name||`医生 #${account.mentor_doctor_id}`):"—"].forEach(value=>{const cell=document.createElement("td");cell.textContent=value;row.append(cell);});
      const stateCell=document.createElement("td"), state=document.createElement("span");state.className=`account-state ${account.is_active?"":"inactive"}`;state.textContent=account.is_active?"启用":"停用";stateCell.append(state);row.append(stateCell);
      const loginCell=document.createElement("td");loginCell.className="account-login-time";loginCell.textContent=account.last_login_at?loginTimeFormat.format(new Date(account.last_login_at)):"暂无记录";row.append(loginCell);
      const actionCell=document.createElement("td"), button=document.createElement("button");button.type="button";button.className="secondary";button.textContent=account.is_active?"停用":"启用";
      button.onclick=async()=>{button.disabled=true;try{await api(`/admin/accounts/${account.id}`,{method:"PATCH",body:JSON.stringify({is_active:!account.is_active})});await load();message("账号状态已更新");}catch(error){message(error.message,true);button.disabled=false;}};
      actionCell.append(button);row.append(actionCell);return row;
    }));
    if(!filtered.length){const row=document.createElement("tr"),cell=document.createElement("td");cell.colSpan=7;cell.textContent="没有匹配的账号。";row.append(cell);$("accounts").append(row);}
  }
  function mentorState(){const student=$("role").value==="student";["mentorLabel","mentorDoctor"].forEach(id=>$(id).classList.toggle("hidden",!student));$("mentorDoctor").required=student;$("mentorDoctor").disabled=!student;}
  async function load(){accounts=await api("/admin/accounts");renderAccounts();const previous=$("mentorDoctor").value;$("mentorDoctor").replaceChildren(new Option("请选择所属医生",""),...accounts.filter(a=>a.role==="doctor"&&a.is_active).map(a=>new Option(`${a.display_name}（${a.username}）`,String(a.id))));$("mentorDoctor").value=previous;mentorState();}
  function activateView(){
    const views={accounts:["账号管理","账号与访问","accountsCard"],"new-account":["开通账号","账号与访问","createAccountCard"],permissions:["角色与权限","平台管理","placeholderCard","医生团队与患者资料的访问授权将在这里管理。"],consents:["须知与同意","平台管理","placeholderCard","患者须知版本与同意记录将在这里管理。"],audit:["操作记录","平台管理","placeholderCard","平台操作记录的查询与核对将在这里管理。"],backups:["数据与备份","平台管理","placeholderCard","资料备份与恢复管理将在这里提供。"]};
    views["doctor-accounts"]=["医生账号","账号与访问","accountsCard"];
    views["student-accounts"]=["学生账号","账号与访问","accountsCard"];
    const key=Object.hasOwn(views,location.hash.slice(1))?location.hash.slice(1):"accounts", [title,group,card,description]=views[key];
    $("roleFilter").value=key==="doctor-accounts"?"doctor":key==="student-accounts"?"student":"";renderAccounts();
    ["accountsCard","createAccountCard","placeholderCard"].forEach(id=>$(id).classList.toggle("hidden",id!==card));
    $("pageTitle").textContent=title;$("breadcrumb").textContent=`${group} / ${title}`;DoctorShell.activate(key);
    $("message").classList.add("hidden");if(description){$("placeholderTitle").textContent=title;$("placeholderDescription").textContent=description;}
  }
  const passwordControls = [["newPassword", "toggleNewPassword", "初始密码"], ["confirmPassword", "toggleConfirmPassword", "确认密码"]];
  function setPasswordVisible(inputId, buttonId, label, visible) {
    $(inputId).type = visible ? "text" : "password";
    $(buttonId).setAttribute("aria-label", `${visible ? "隐藏" : "显示"}${label}`);
    $(buttonId).setAttribute("aria-pressed", String(visible));
  }
  passwordControls.forEach(([inputId, buttonId, label]) => {
    $(buttonId).onclick = () => setPasswordVisible(inputId, buttonId, label, $(inputId).type === "password");
    $(inputId).addEventListener("input", () => $("confirmPassword").setCustomValidity(""));
  });
  $("accountForm").onreset = () => {
    setTimeout(mentorState,0);
    passwordControls.forEach(([inputId, buttonId, label]) => setPasswordVisible(inputId, buttonId, label, false));
    $("confirmPassword").setCustomValidity("");
  };
  $("accountForm").onsubmit=async event=>{event.preventDefault();
    if ($("newPassword").value !== $("confirmPassword").value) {
      $("confirmPassword").setCustomValidity("两次输入的密码不一致，请重新输入。");
      $("confirmPassword").reportValidity();
      return;
    }
    const button=event.target.querySelector('button[type="submit"]');button.disabled=true;try{
    await api("/admin/accounts",{method:"POST",body:JSON.stringify({username:$("newUsername").value,display_name:$("displayName").value,password:$("newPassword").value,role:$("role").value,mentor_doctor_id:$("role").value==="student"?Number($("mentorDoctor").value):null})});
    event.target.reset();await load();history.replaceState(null,"",AppPaths.url("/admin#accounts"));activateView();message("账号已开通");
  }catch(error){message(error.message,true);}finally{button.disabled=false;}};
  ["accountSearch","roleFilter","statusFilter"].forEach(id=>$(id).addEventListener(id==="accountSearch"?"input":"change",renderAccounts));
  $("refresh").onclick=()=>load().catch(error=>message(error.message,true));
  $("role").onchange=mentorState;
  $("logout").onclick=()=>AppSession.logout("admin");
  window.addEventListener("hashchange",activateView);
  async function init(){if(!token)return;try{const me=await api("/auth/me");if(me.role!=="admin"){AppSession.logout("admin");return;}DoctorShell.setUser(me.display_name);await load();activateView();}catch(error){message(error.message,true);}}
  init();
})();
