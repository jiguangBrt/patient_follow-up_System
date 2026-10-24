(() => {
  const roles = {patient: {path: "/patient", name: "患者"}, doctor: {path: "/doctor", name: "医生"}, admin: {path: "/admin", name: "管理员"}};
  Object.values(roles).forEach(role => { role.path = AppPaths.url(role.path); });
  function clear() { Object.keys(roles).forEach(role => AppPaths.storage.removeItem(`${role}Token`)); AppPaths.storage.removeItem("activeRole"); }
  window.AppSession = {
    roles,
    save(token, role) { if (!roles[role]) throw new Error("账号身份无效"); clear(); AppPaths.storage.setItem(`${role}Token`, token); AppPaths.storage.setItem("activeRole", role); },
    require(role) { const token = AppPaths.storage.getItem(`${role}Token`); if (!token) location.replace(AppPaths.url(`/?role=${role}`)); return token; },
    logout(role, expired = false) { clear(); location.replace(AppPaths.url(`/?role=${role}${expired ? "&expired=1" : ""}`)); },
  };
})();
