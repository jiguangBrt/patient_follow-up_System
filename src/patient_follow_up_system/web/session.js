(() => {
  const roles = {patient: {path: "/patient", name: "患者"}, doctor: {path: "/doctor", name: "医生"}, admin: {path: "/admin", name: "管理员"}};
  function clear() { Object.keys(roles).forEach(role => sessionStorage.removeItem(`${role}Token`)); sessionStorage.removeItem("activeRole"); }
  window.AppSession = {
    roles,
    save(token, role) { if (!roles[role]) throw new Error("账号身份无效"); clear(); sessionStorage.setItem(`${role}Token`, token); sessionStorage.setItem("activeRole", role); },
    require(role) { const token = sessionStorage.getItem(`${role}Token`); if (!token) location.replace(`/?role=${role}`); return token; },
    logout(role, expired = false) { clear(); location.replace(`/?role=${role}${expired ? "&expired=1" : ""}`); },
  };
})();
