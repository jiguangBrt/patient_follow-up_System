(() => {
  const $ = id => document.getElementById(id);
  const descriptions = {patient:"查看本人档案，向医生提交就诊资料。", doctor:"管理患者档案，核对病历，管理学生及患者授权。", student:"在所属医生授权范围内整理患者资料。", admin:"管理平台账号，维护账号的启用状态。"};
  let selectedRole = "doctor";
  let busy = false;
  function chooseRole(role) {
    if (busy || !Object.hasOwn(AppSession.roles, role)) return;
    selectedRole = role;
    document.querySelectorAll("[role='tab']").forEach(tab => { const selected = tab.dataset.role === role; tab.setAttribute("aria-selected", String(selected)); tab.tabIndex = selected ? 0 : -1; });
    $("loginPanel").setAttribute("aria-labelledby", `tab-${role}`);
    $("roleDescription").textContent = descriptions[role];
    $("submitLogin").replaceChildren(document.createTextNode(role === "patient" ? "进入我的档案" : `登录${AppSession.roles[role].name}${role === "doctor" ? "工作台" : "工作区"}`));
    $("patientHelp").hidden = role !== "patient";
    $("loginMessage").textContent = "";
    const url = new URL(location.href); url.searchParams.set("role", role); url.searchParams.delete("expired"); history.replaceState(null, "", url.pathname + url.search);
  }
  document.querySelectorAll("[role='tab']").forEach(tab => {
    tab.onclick = () => chooseRole(tab.dataset.role);
    tab.onkeydown = event => { const tabs = [...document.querySelectorAll("[role='tab']")]; const index = tabs.indexOf(tab); const offset = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0; if (!offset && event.key !== "Home" && event.key !== "End") return; event.preventDefault(); const target = tabs[event.key === "Home" ? 0 : event.key === "End" ? tabs.length-1 : (index + offset + tabs.length) % tabs.length]; chooseRole(target.dataset.role); target.focus(); };
  });
  $("togglePassword").onclick = () => { const visible = $("password").type === "password"; $("password").type = visible ? "text" : "password"; $("togglePassword").setAttribute("aria-label", visible ? "隐藏密码" : "显示密码"); $("togglePassword").setAttribute("aria-pressed", String(visible)); };
  $("loginForm").onsubmit = async event => {
    event.preventDefault(); if (busy) return;
    busy = true; const role = selectedRole;
    $("submitLogin").disabled = true; document.querySelectorAll("[role='tab']").forEach(tab => { tab.disabled = true; }); $("loginMessage").textContent = "";
    try {
      const response = await AppPaths.fetch("/auth/login", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({username:$("username").value.trim(), password:$("password").value, role})});
      const result = await response.json();
      if (!response.ok) throw new Error(response.status === 401 ? "账号或密码不正确，或账号已被停用。" : typeof result.detail === "string" ? result.detail : "请检查账号和密码。" );
      const meResponse = await AppPaths.fetch("/auth/me", {headers:{Authorization:`Bearer ${result.access_token}`}}); const me = await meResponse.json();
      if (!meResponse.ok || me.role !== role) throw new Error("账号身份与所选入口不一致，请核对后重试。");
      AppSession.save(result.access_token, me.role); $("password").value = ""; location.replace(AppSession.roles[me.role].path);
    } catch(error) { $("loginMessage").textContent = error instanceof TypeError ? "暂时无法连接服务，请稍后重试。" : error.message; }
    finally { busy = false; $("submitLogin").disabled = false; document.querySelectorAll("[role='tab']").forEach(tab => { tab.disabled = false; }); }
  };
  const params = new URLSearchParams(location.search); const expired = params.get("expired") === "1";
  chooseRole(Object.hasOwn(AppSession.roles, params.get("role")) ? params.get("role") : "doctor");
  if (expired) $("loginMessage").textContent = "登录已失效或账号已被停用，请重新登录。";
})();
