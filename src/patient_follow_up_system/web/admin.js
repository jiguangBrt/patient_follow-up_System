const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("adminToken");
function message(text, error = false) { $("message").textContent = text; $("message").className = `status ${error ? "error" : "success"}`; }
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {"Content-Type":"application/json", ...(token ? {Authorization:`Bearer ${token}`} : {})}});
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) { sessionStorage.removeItem("adminToken"); token = null; $("workspace").classList.add("hidden"); $("loginCard").classList.remove("hidden"); }
    throw new Error(typeof data.detail === "string" ? data.detail : "请检查输入内容");
  }
  return data;
}
async function load() {
  const accounts = await api("/admin/accounts");
  $("loginCard").classList.add("hidden"); $("workspace").classList.remove("hidden");
  $("accounts").replaceChildren(...accounts.map(account => {
    const row = document.createElement("article"); row.className = "patient";
    const info = document.createElement("div");
    info.textContent = `${account.display_name} · ${account.username} · ${account.role === "doctor" ? "医生" : "患者"} · ${account.is_active ? "启用" : "停用"}`;
    const button = document.createElement("button"); button.textContent = account.is_active ? "停用" : "启用";
    button.onclick = async () => { button.disabled = true; try { await api(`/admin/accounts/${account.id}`, {method:"PATCH", body:JSON.stringify({is_active:!account.is_active})}); await load(); message("账号状态已更新"); } catch(e) { message(e.message,true); button.disabled = false; } };
    row.append(info,button); return row;
  }));
}
$("loginForm").onsubmit = async event => { event.preventDefault(); try {
  const result = await api("/auth/login", {method:"POST",body:JSON.stringify({username:$("username").value,password:$("password").value})});
  token = result.access_token;
  const me = await api("/auth/me"); if(me.role !== "admin") { token = null; throw new Error("请使用管理员账号登录"); }
  sessionStorage.setItem("adminToken",token); $("password").value = ""; await load();
} catch(e) { message(e.message,true); } };
$("accountForm").onsubmit = async event => { event.preventDefault(); const button = event.target.querySelector("button"); button.disabled=true; try {
  await api("/admin/accounts", {method:"POST",body:JSON.stringify({username:$("newUsername").value,display_name:$("displayName").value,password:$("newPassword").value,role:$("role").value})});
  event.target.reset(); await load(); message("测试账号已开通");
} catch(e) { message(e.message,true); } finally { button.disabled=false; } };
$("logout").onclick = () => { sessionStorage.removeItem("adminToken"); location.reload(); };
$("refresh").onclick = () => load().catch(e=>message(e.message,true));
if(token) load().catch(e=>message(e.message,true));
