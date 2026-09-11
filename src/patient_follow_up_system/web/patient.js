const $ = (id) => document.getElementById(id);
let patientToken = sessionStorage.getItem("patientToken");
let currentPatient = null;
let currentNotice = null;

function patientMessage(text, error = false) {
  $("patientMessage").textContent = text;
  $("patientMessage").className = `status ${error ? "error" : "success"}`;
}

async function patientApi(path, options = {}) {
  options.headers = {
    "Content-Type": "application/json",
    ...(patientToken ? { Authorization: `Bearer ${patientToken}` } : {}),
  };
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.detail || "请求失败");
    error.status = response.status;
    throw error;
  }
  return data;
}

async function loadPatientHome() {
  try {
    const me = await patientApi("/auth/me");
    if (me.role !== "patient") {
      const error = new Error("该账号不是患者账号，请使用患者账号登录。");
      error.status = 403;
      throw error;
    }
    const patients = await patientApi("/patients");
    if (!patients.length) {
      throw new Error("当前账号尚未关联患者档案，请使用医生提供的专属邀请完成认领。");
    }
    const patient = patients[0];
    const [encounters, notice, documents] = await Promise.all([
      patientApi(`/patients/${patient.id}/encounters`),
      fetch("/patient-notices/current").then(async response => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "患者须知暂不可用");
        return data;
      }),
      patientApi(`/patients/${patient.id}/documents`),
    ]);
    currentPatient = patient;
    currentNotice = notice;
    $("patientLoginCard").classList.add("hidden");
    $("patientHome").classList.remove("hidden");
    $("patientName").textContent = patient.display_name;
    $("patientCode").textContent = patient.patient_code;
    $("patientStatus").textContent = "账号已关联，可以查看本人档案";
    $("patientStatus").className = "status success";
    $("patientNotice").textContent = `${notice.title} · 版本 ${notice.version}`;
    renderPatientDocuments(documents);
    if (!encounters.length) {
      $("patientEncounters").textContent = "目前没有就诊记录。";
    } else {
      $("patientEncounters").replaceChildren(...encounters.map(encounter => {
        const item = document.createElement("div");
        item.className = "encounter-item";
        const text = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = encounter.display_label;
        const meta = document.createElement("div");
        meta.className = "muted";
        meta.textContent = `${encounter.encounter_code} · ${new Date(encounter.occurred_at).toLocaleString()}`;
        text.append(title, meta);
        item.append(text);
        return item;
      }));
    }
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      patientToken = null;
      sessionStorage.removeItem("patientToken");
      $("patientHome").classList.add("hidden");
      $("patientLoginCard").classList.remove("hidden");
    }
    patientMessage(error.message || "患者中心暂时无法加载", true);
  }
}

function renderPatientDocuments(documents) {
  if (!documents.length) {
    $("patientDocuments").textContent = "尚未提交随访资料。";
    return;
  }
  const statusLabels = { pending: "等待医生审核", approved: "医生已确认", rejected: "未通过审核" };
  $("patientDocuments").replaceChildren(...documents.map(record => {
    const item = document.createElement("article");
    item.className = `timeline-item ${record.review_status}`;
    const date = record.confirmed_event_date || record.event_date;
    const title = record.confirmed_label || record.display_label;
    const heading = document.createElement("strong");
    heading.textContent = `${date} · ${title}`;
    const state = document.createElement("p");
    state.textContent = statusLabels[record.review_status] || record.review_status;
    const summary = document.createElement("p");
    summary.textContent = record.doctor_summary || "资料原件已保存，尚未形成医生确认摘要。";
    const meta = document.createElement("p");
    meta.className = "muted";
    meta.textContent = `${record.original_name} · OCR 未运行 · 须知版本 ${record.notice_version}`;
    const sourceButton = document.createElement("button");
    sourceButton.type = "button";
    sourceButton.className = "secondary";
    sourceButton.textContent = "查看我提交的原始资料";
    sourceButton.onclick = () => openOwnPatientDocument(record.id);
    item.append(heading, state, summary, meta, sourceButton);
    return item;
  }));
}

async function openOwnPatientDocument(documentId) {
  const response = await fetch(`/patient-documents/${documentId}/file`, {
    headers: { Authorization: `Bearer ${patientToken}` },
  });
  if (!response.ok) {
    patientMessage("原始资料暂时无法打开。", true);
    return;
  }
  const url = URL.createObjectURL(await response.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function fileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.onerror = () => reject(new Error("无法读取所选文件"));
    reader.readAsDataURL(file);
  });
}

$("patientLoginForm").onsubmit = async (event) => {
  event.preventDefault();
  try {
    const login = await patientApi("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: $("patientUsername").value.trim(),
        password: $("patientPassword").value,
      }),
    });
    patientToken = login.access_token;
    sessionStorage.setItem("patientToken", patientToken);
    $("patientPassword").value = "";
    $("patientMessage").classList.add("hidden");
    await loadPatientHome();
  } catch (error) {
    if (error.status === 403) {
      patientToken = null;
      sessionStorage.removeItem("patientToken");
    }
    $("patientPassword").value = "";
    patientMessage(
      error.status === 403
        ? "该账号不是患者账号，请使用患者账号登录。"
        : "账号或密码不正确，请重试。",
      true,
    );
  }
};

$("patientLogout").onclick = () => {
  sessionStorage.removeItem("patientToken");
  location.reload();
};

$("showDocumentUpload").onclick = () => {
  $("documentUploadForm").classList.remove("hidden");
  $("documentEventDate").value = new Date().toISOString().slice(0, 10);
  $("documentUploadForm").scrollIntoView({ behavior: "smooth", block: "start" });
};

$("cancelDocumentUpload").onclick = () => $("documentUploadForm").classList.add("hidden");

$("documentUploadForm").onsubmit = async (event) => {
  event.preventDefault();
  if (!currentPatient || !currentNotice) return;
  const file = $("patientDocumentFile").files[0];
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) {
    patientMessage("资料不能超过 8 MB。", true);
    return;
  }
  const submitButton = event.submitter;
  if (submitButton) submitButton.disabled = true;
  try {
    const documentBase64 = await fileAsBase64(file);
    await patientApi(`/patients/${currentPatient.id}/documents`, {
      method: "POST",
      body: JSON.stringify({
        event_date: $("documentEventDate").value,
        display_label: $("documentLabel").value.trim(),
        patient_note: $("documentNote").value.trim() || null,
        notice_version_id: currentNotice.id,
        consent_given: $("documentConsent").checked,
        document_name: file.name,
        document_mime_type: file.type,
        document_base64: documentBase64,
      }),
    });
    event.target.reset();
    $("documentUploadForm").classList.add("hidden");
    patientMessage("资料已提交，正在等待医生审核。", false);
    await loadPatientHome();
  } catch (error) {
    patientMessage(error.message || "资料提交失败，请重试。", true);
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
};

$("showNoAccount").onclick = () => {
  const help = $("noAccountHelp");
  const willShow = help.classList.contains("hidden");
  help.classList.toggle("hidden", !willShow);
  $("showNoAccount").textContent = willShow ? "收起开户说明" : "我还没有账号";
};

if (patientToken) loadPatientHome();
