(() => {
  const isAdmin = document.body.dataset.workspaceRole === "admin";
  const paths = {
    patients: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M16 3a4 4 0 0 1 0 8"/><circle cx="9" cy="7" r="4"/>',
    intakes: '<path d="M9 5H5v16h14V5h-4M9 3h6v4H9zM8 12h8m-8 4h5"/>',
    clinical: '<path d="M14 2H6v20h12V6zM14 2v5h5M9 12h6m-6 4h6"/>',
    followups: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18m-12 5 2 2 4-4"/>',
    cohorts: '<circle cx="8" cy="8" r="3"/><circle cx="17" cy="8" r="3"/><path d="M2 21v-2a6 6 0 0 1 12 0v2m1-8a6 6 0 0 1 7 6v2"/>',
    exports: '<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
    notice: '<path d="M6 3h12v18H6zM9 7h6m-6 4h6m-6 4h4"/>',
    accounts: '<circle cx="9" cy="7" r="4"/><path d="M2 21v-2a7 7 0 0 1 14 0v2m2-13h4m-2-2v4"/>',
    "new-account": '<path d="M14 2H6v20h12V6zM14 2v5h5M12 11v6m-3-3h6"/>',
    permissions: '<path d="M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6zM8 12l3 3 5-6"/>',
    consents: '<path d="M6 3h12v18H6zM9 7h6m-6 4h6m-6 5 2 2 4-4"/>',
    audit: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    backups: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 4 18 4 18 0V5M3 12c0 4 18 4 18 0"/>',
  };
  const groups = isAdmin ? [
    ["账号与访问", [["accounts", "账号管理"], ["new-account", "开通账号"]]],
    ["平台管理", [["permissions", "角色与权限", true], ["consents", "须知与同意", true], ["audit", "操作记录", true], ["backups", "数据与备份", true]]],
  ] : [
    ["诊疗管理", [["patients", "患者管理"], ["intakes", "建档申请"], ["clinical", "病例识别与审核"]]],
    ["随访与科研", [["followups", "随访计划", true], ["cohorts", "科研队列", true], ["exports", "资料导出", true]]],
    ["设置", [["notice", "患者须知"]]],
  ];
  const root = document.getElementById("doctorSidebar");
  root.innerHTML = '<div class="doctor-brand"><span class="brand-mark">随</span><div>随访工作台<small>临床资料管理</small></div></div><nav aria-label="医生工作区"></nav><div class="sidebar-footer"><a href="/patient" target="_blank" rel="noreferrer">患者端预览 ↗</a><div class="sidebar-profile"><span class="profile-avatar">医</span><div><strong id="sidebarUser">医生</strong><small>医生工作区</small></div><button id="logout" title="退出登录" aria-label="退出登录">退出</button></div></div>';
  if (isAdmin) {
    root.querySelector("nav").setAttribute("aria-label", "管理员工作区");
    root.querySelector(".doctor-brand small").textContent = "平台管理";
    const entry = root.querySelector(".sidebar-footer > a"); entry.href = "/"; entry.removeAttribute("target"); entry.textContent = "统一登录入口 ↗";
    root.querySelector(".profile-avatar").textContent = "管";
    root.querySelector(".sidebar-profile small").textContent = "管理员工作区";
    root.querySelector("#sidebarUser").textContent = "管理员";
  }
  const nav = root.querySelector("nav");
  groups.forEach(([label, items]) => {
    const group = document.createElement("div"); group.className = "nav-group";
    const title = document.createElement("p"); title.textContent = label; group.append(title);
    items.forEach(([key, text, planned]) => {
      const link = document.createElement("a"); link.dataset.view = key;
      link.href = isAdmin ? `#${key}` : key === "clinical" ? "/clinical" : (location.pathname === "/doctor" ? "" : "/doctor") + "#" + key;
      link.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[key]}</svg>`;
      const name = document.createElement("span"); name.textContent = text; link.append(name);
      if (planned) { const badge = document.createElement("small"); badge.textContent = "待建设"; link.append(badge); }
      group.append(link);
    });
    nav.append(group);
  });
  window.DoctorShell = {
    activate(view) { root.querySelectorAll("[data-view]").forEach(link => { link.classList.toggle("active", link.dataset.view === view); if(link.dataset.view === view) link.setAttribute("aria-current","page"); else link.removeAttribute("aria-current"); }); },
    setUser(name) { document.getElementById("sidebarUser").textContent = name; },
  };
  DoctorShell.activate(location.pathname === "/clinical" ? "clinical" : location.hash.slice(1) || (isAdmin ? "accounts" : "patients"));
})();
