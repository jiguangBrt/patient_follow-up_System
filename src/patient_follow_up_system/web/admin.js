(() => {
  const $ = id => document.getElementById(id);
  const token = AppSession.require("admin");
  let accounts = [];
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
      [account.display_name,account.username,account.role==="doctor"?"医生":"患者"].forEach(value=>{const cell=document.createElement("td");cell.textContent=value;row.append(cell);});
      const stateCell=document.createElement("td"), state=document.createElement("span");state.className=`account-state ${account.is_active?"":"inactive"}`;state.textContent=account.is_active?"启用":"停用";stateCell.append(state);row.append(stateCell);
      const actionCell=document.createElement("td"), button=document.createElement("button");button.type="button";button.className="secondary";button.textContent=account.is_active?"停用":"启用";
      button.onclick=async()=>{button.disabled=true;try{await api(`/admin/accounts/${account.id}`,{method:"PATCH",body:JSON.stringify({is_active:!account.is_active})});await load();message("账号状态已更新");}catch(error){message(error.message,true);button.disabled=false;}};
      actionCell.append(button);row.append(actionCell);return row;
    }));
    if(!filtered.length){const row=document.createElement("tr"),cell=document.createElement("td");cell.colSpan=5;cell.textContent="没有匹配的账号。";row.append(cell);$("accounts").append(row);}
  }
  async function load(){accounts=await api("/admin/accounts");renderAccounts();}
  function activateView(){
    const views={accounts:["账号管理","账号与访问","accountsCard"],"new-account":["开通账号","账号与访问","createAccountCard"],permissions:["角色与权限","平台管理","placeholderCard","医生团队与患者资料的访问授权将在这里管理。"],consents:["须知与同意","平台管理","placeholderCard","患者须知版本与同意记录将在这里管理。"],audit:["操作记录","平台管理","placeholderCard","平台操作记录的查询与核对将在这里管理。"],backups:["数据与备份","平台管理","placeholderCard","资料备份与恢复管理将在这里提供。"]};
    const key=Object.hasOwn(views,location.hash.slice(1))?location.hash.slice(1):"accounts", [title,group,card,description]=views[key];
    ["accountsCard","createAccountCard","placeholderCard"].forEach(id=>$(id).classList.toggle("hidden",id!==card));
    $("pageTitle").textContent=title;$("breadcrumb").textContent=`${group} / ${title}`;DoctorShell.activate(key);
    $("message").classList.add("hidden");if(description){$("placeholderTitle").textContent=title;$("placeholderDescription").textContent=description;}
  }
  $("accountForm").onsubmit=async event=>{event.preventDefault();const button=event.target.querySelector("button");button.disabled=true;try{
    await api("/admin/accounts",{method:"POST",body:JSON.stringify({username:$("newUsername").value,display_name:$("displayName").value,password:$("newPassword").value,role:$("role").value})});
    event.target.reset();await load();history.replaceState(null,"","/admin#accounts");activateView();message("账号已开通");
  }catch(error){message(error.message,true);}finally{button.disabled=false;}};
  ["accountSearch","roleFilter","statusFilter"].forEach(id=>$(id).addEventListener(id==="accountSearch"?"input":"change",renderAccounts));
  $("refresh").onclick=()=>load().catch(error=>message(error.message,true));
  $("logout").onclick=()=>AppSession.logout("admin");
  window.addEventListener("hashchange",activateView);
  async function init(){if(!token)return;try{const me=await api("/auth/me");if(me.role!=="admin"){AppSession.logout("admin");return;}DoctorShell.setUser(me.display_name);await load();activateView();}catch(error){message(error.message,true);}}
  init();
})();
