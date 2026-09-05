const $ = (id) => document.getElementById(id);
let auth = sessionStorage.getItem("patientToken");
let invitationToken = new URLSearchParams(location.hash.slice(1)).get("token")
  || sessionStorage.getItem("invitationToken");

if (invitationToken) {
  sessionStorage.setItem("invitationToken", invitationToken);
  history.replaceState(null, "", location.pathname);
}

const labels = {
  available: "邀请有效，请完成下方核验",
  expired: "邀请已过期，请联系医护人员重新生成",
  revoked: "邀请已撤销，请联系医护人员",
  exhausted: "邀请已使用，无需重复绑定",
  locked: "输错次数过多，邀请已锁定",
  unavailable: "邀请不可用，请联系医护人员",
};

function show(text, error = false) {
  $("status").textContent = text;
  $("status").className = `status ${error ? "error" : "success"}`;
}

async function request(path, body, withAuth = false) {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(withAuth && auth ? { Authorization: `Bearer ${auth}` } : {}),
    },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.detail || "请求失败");
    error.status = response.status;
    throw error;
  }
  return data;
}

function showBindForm() {
  $("bindForm").classList.remove("hidden");
  if (auth) $("accountFields").classList.add("hidden");
}

async function check() {
  $("title").textContent = "邀请状态";
  if (!invitationToken) {
    show(labels.unavailable, true);
    return;
  }
  try {
    const data = await request("/invitations/status", {
      invitation_token: invitationToken,
    });
    show(labels[data.state] || labels.unavailable, data.state !== "available");
    if (data.state === "available") showBindForm();
  } catch {
    show(labels.unavailable, true);
  }
}

$("code").addEventListener("input", (event) => {
  event.target.value = event.target.value.replace(/\D/g, "").slice(0, 6);
});

$("bindForm").onsubmit = async (event) => {
  event.preventDefault();
  const button = $("submitButton");
  button.disabled = true;
  try {
    if (!auth) {
      const login = await request("/auth/login", {
        username: $("username").value,
        password: $("password").value,
      });
      auth = login.access_token;
      sessionStorage.setItem("patientToken", auth);
      $("password").value = "";
    }
    const result = await request("/invitations/bind", {
      invitation_token: invitationToken,
      verification_code: $("code").value,
    }, true);
    $("bindForm").classList.add("hidden");
    $("done").classList.remove("hidden");
    show(result.already_bound ? "该账号已经绑定本人档案" : "核验成功");
    sessionStorage.removeItem("invitationToken");
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      auth = null;
      sessionStorage.removeItem("patientToken");
      $("accountFields").classList.remove("hidden");
    }
    show("信息未核验通过，请检查后重试或请医护人员重新生成邀请", true);
    button.disabled = false;
  }
};

check();
