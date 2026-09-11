const $ = (id) => document.getElementById(id);
let token = sessionStorage.getItem("doctorToken");
let currentInvitationId = null;
let currentIntakeLinkId = null;
let selectedPatient = null;

function message(text, error = false) {
  $("message").textContent = text;
  $("message").className = `status ${error ? "error" : "success"}`;
}

async function api(path, options = {}) {
  options.headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) throw new Error(data?.detail || `请求失败（${response.status}）`);
  return data;
}

function actionButton(text, action, secondary = false) {
  const button = document.createElement("button");
  button.textContent = text;
  if (secondary) button.className = "secondary";
  button.onclick = action;
  return button;
}

function detailLine(label, value) {
  const row = document.createElement("p");
  const strong = document.createElement("strong");
  strong.textContent = `${label}：`;
  row.append(strong, document.createTextNode(value));
  return row;
}

async function showPatientDetails(patient, details) {
  if (!details.classList.contains("hidden")) {
    details.classList.add("hidden");
    return;
  }
  details.classList.remove("hidden");
  details.replaceChildren(
    detailLine("系统患者编号", patient.patient_code),
    detailLine("显示名称", patient.display_name),
    detailLine("账号绑定状态", patient.is_bound ? "已绑定" : "尚未绑定"),
    detailLine("建档时间", new Date(patient.created_at).toLocaleString()),
  );
  try {
    const [encounters, documents] = await Promise.all([
      api(`/patients/${patient.id}/encounters`),
      api(`/patients/${patient.id}/documents`),
    ]);
    const timelineHeading = document.createElement("h4");
    timelineHeading.textContent = "随访资料与时间轴";
    details.append(timelineHeading);
    if (!documents.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "尚无患者提交的随访资料。";
      details.append(empty);
    } else {
      documents.forEach(record => details.append(doctorDocumentCard(record, patient, details)));
    }

    const heading = document.createElement("h4");
    heading.textContent = "模拟就诊记录";
    details.append(heading);
    if (!encounters.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "尚无模拟就诊记录。";
      details.append(empty);
    } else {
      encounters.forEach((encounter) => {
        const item = document.createElement("div");
        item.className = "encounter-item";
        const text = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = encounter.display_label;
        const meta = document.createElement("div");
        meta.className = "muted";
        meta.textContent = `${encounter.encounter_code} · ${new Date(encounter.occurred_at).toLocaleString()}`;
        text.append(title, meta);
        item.append(text, actionButton("为本次就诊生成邀请", () => createInvite(patient.id, encounter.id), true));
        details.append(item);
      });
    }
  } catch (error) {
    message(error.message, true);
  }
}

function doctorDocumentCard(record, patient, details) {
  const item = document.createElement("article");
  item.className = `timeline-item ${record.review_status}`;
  item.append(
    detailLine("患者填写", `${record.event_date} · ${record.display_label}`),
    detailLine("患者说明", record.patient_note || "未填写"),
    detailLine("审核状态", { pending: "待审核", approved: "已确认进入时间轴", rejected: "已驳回" }[record.review_status]),
    detailLine("资料处理", record.extraction_status === "not_run" ? "OCR 未运行，等待人工审核" : record.extraction_status),
    detailLine("须知记录", `${record.notice_version} · ${new Date(record.consented_at).toLocaleString()}`),
  );
  item.append(actionButton("查看原始资料", () => openPatientDocument(record.id), true));
  if (record.review_status === "approved") {
    item.append(
      detailLine("确认事件", `${record.confirmed_event_date} · ${record.confirmed_label}`),
      detailLine("医生摘要", record.doctor_summary),
    );
  } else if (record.review_status === "rejected") {
    item.append(detailLine("审核说明", record.doctor_summary || "未填写"));
  } else {
    const form = document.createElement("div");
    form.className = "review-grid";
    const dateLabel = document.createElement("label");
    dateLabel.textContent = "确认事件日期";
    const dateInput = document.createElement("input");
    dateInput.type = "date";
    dateInput.value = record.event_date;
    const titleLabel = document.createElement("label");
    titleLabel.textContent = "确认资料名称";
    const titleInput = document.createElement("input");
    titleInput.value = record.display_label;
    titleInput.maxLength = 100;
    const summaryLabel = document.createElement("label");
    summaryLabel.textContent = "医生确认摘要";
    const summaryInput = document.createElement("textarea");
    summaryInput.maxLength = 1000;
    summaryInput.placeholder = "仅填写从虚构或去标识化原件中人工确认的内容";
    form.append(dateLabel, dateInput, titleLabel, titleInput, summaryLabel, summaryInput);
    const actions = document.createElement("div");
    actions.className = "row full-row";
    actions.append(
      actionButton("确认并进入时间轴", () => reviewPatientDocument(record.id, "approve", {
        confirmed_event_date: dateInput.value,
        confirmed_label: titleInput.value.trim(),
        doctor_summary: summaryInput.value.trim(),
      }, patient, details)),
      actionButton("驳回资料", () => reviewPatientDocument(record.id, "reject", {
        doctor_summary: summaryInput.value.trim() || null,
      }, patient, details), true),
    );
    form.append(actions);
    item.append(form);
  }
  return item;
}

async function openPatientDocument(documentId) {
  const response = await fetch(`/patient-documents/${documentId}/file`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) { message("原始资料暂时无法打开", true); return; }
  const url = URL.createObjectURL(await response.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

async function reviewPatientDocument(documentId, action, fields, patient, details) {
  try {
    await api(`/patient-documents/${documentId}/review`, {
      method: "POST",
      body: JSON.stringify({ action, ...fields }),
    });
    message(action === "approve" ? "资料已确认并进入患者时间轴" : "资料已驳回");
    details.classList.add("hidden");
    await showPatientDetails(patient, details);
  } catch (error) {
    message(error.message, true);
  }
}

function patientCard(patient) {
  const card = document.createElement("article");
  card.className = "patient-card-wide";
  const summary = document.createElement("div");
  summary.className = "patient-summary";
  const text = document.createElement("div");
  const name = document.createElement("h3");
  name.textContent = patient.display_name;
  const code = document.createElement("div");
  code.className = "muted";
  code.textContent = patient.patient_code;
  const badge = document.createElement("span");
  badge.className = `badge ${patient.is_bound ? "bound" : "unbound"}`;
  badge.textContent = patient.is_bound ? "已关联患者账号" : "尚未关联患者账号";
  badge.title = patient.is_bound ? "患者可使用自己的账号访问该档案" : "档案已建立，等待患者通过专属邀请认领";
  text.append(name, code, badge);
  const actions = document.createElement("div");
  actions.className = "row patient-actions";
  const details = document.createElement("div");
  details.className = "patient-details hidden";
  actions.append(
    actionButton("基本情况", () => showPatientDetails(patient, details), true),
    actionButton("新增就诊", () => openEncounterForm(patient), true),
    actionButton("生成邀请", () => createInvite(patient.id)),
  );
  summary.append(text, actions);
  card.append(summary, details);
  return card;
}

async function loadPatients() {
  try {
    const items = await api("/patients");
    $("loginCard").classList.add("hidden");
    $("patientsCard").classList.remove("hidden");
    $("patients").replaceChildren(...items.map(patientCard));
  } catch (error) {
    sessionStorage.removeItem("doctorToken");
    token = null;
    message(error.message, true);
  }
}

function openEncounterForm(patient) {
  selectedPatient = patient;
  $("encounterTitle").textContent = `为 ${patient.display_name} 新增模拟就诊`;
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  $("occurredAt").value = now.toISOString().slice(0, 16);
  $("encounterCard").classList.remove("hidden");
  $("encounterCard").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function createInvite(patientId, encounterId = null) {
  try {
    const data = await api(`/patients/${patientId}/invitations`, {
      method: "POST",
      body: JSON.stringify({
        encounter_id: encounterId,
        expires_in_minutes: 60,
        max_uses: 1,
      }),
    });
    currentInvitationId = data.id;
    $("qr").innerHTML = data.qr_svg;
    $("code").textContent = data.verification_code;
    $("openInvite").href = data.invitation_url;
    $("expiry").textContent = `有效期至 ${new Date(data.expires_at).toLocaleString()}`;
    $("inviteCard").classList.remove("hidden");
    $("inviteCard").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    message(error.message, true);
  }
}

async function createIntakeLink() {
  try {
    const data = await api("/intake-links", { method: "POST", body: "{}" });
    currentIntakeLinkId = data.id;
    $("intakeQr").innerHTML = data.qr_svg;
    $("openIntake").href = data.intake_url;
    $("intakeExpiry").textContent = `有效期至 ${new Date(data.expires_at).toLocaleString()}`;
    $("intakeLinkCard").classList.remove("hidden");
    $("intakeLinkCard").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    message(error.message, true);
  }
}

async function reviewIntake(submission, action) {
  try {
    await api(`/intake-submissions/${submission.id}/review`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });
    message(action === "approve" ? "申请已批准并进入患者库" : "申请已驳回");
    await loadIntakes();
    await loadPatients();
  } catch (error) {
    message(error.message, true);
  }
}

async function openIntakeDocument(submissionId) {
  const response = await fetch(`/intake-submissions/${submissionId}/document`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) { message("原始资料暂时无法打开", true); return; }
  const url = URL.createObjectURL(await response.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

async function loadIntakes() {
  try {
    const items = await api("/intake-submissions");
    $("intakesCard").classList.remove("hidden");
    $("intakes").replaceChildren(...items.map((submission) => {
      const item = document.createElement("article");
      item.className = "patient-card-wide";
      item.append(
        detailLine("演示称呼", submission.display_name),
        detailLine("基本信息", `${submission.sex} · ${submission.date_of_birth} · ${submission.operator_relationship}`),
        detailLine("状态", submission.status),
        detailLine("演示同意", submission.consented_at ? `${submission.notice_version} · ${new Date(submission.consented_at).toLocaleString()}${submission.consent_is_legacy_incomplete ? " · 历史内容快照不完整" : ""}` : "未记录"),
        detailLine("资料处理", submission.extraction_status === "pending" ? "原件已保存，待提取/审核" : submission.extraction_status),
      );
      item.append(actionButton("查看原始资料", () => openIntakeDocument(submission.id), true));
      if (submission.status === "pending") {
        const actions = document.createElement("div");
        actions.className = "row";
        actions.append(
          actionButton("批准并生成患者编号", () => reviewIntake(submission, "approve")),
          actionButton("驳回", () => reviewIntake(submission, "reject"), true),
        );
        item.append(actions);
      }
      return item;
    }));
  } catch (error) {
    message(error.message, true);
  }
}

async function loadCurrentNotice() {
  try {
    const notice = await api("/doctor/patient-notices/current");
    $("doctorNoticeSummary").textContent = `${notice.title} · 版本 ${notice.version} · 已发布并生效`;
    $("noticeCard").classList.remove("hidden");
  } catch (error) { message(error.message, true); }
}

$("loginForm").onsubmit = async (event) => {
  event.preventDefault();
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: $("username").value,
        password: $("password").value,
      }),
    });
    token = data.access_token;
    sessionStorage.setItem("doctorToken", token);
    $("password").value = "";
    await Promise.all([loadPatients(), loadCurrentNotice()]);
  } catch (error) {
    message(error.message, true);
  }
};

$("newPatientForm").onsubmit = async (event) => {
  event.preventDefault();
  try {
    await api("/patients", {
      method: "POST",
      body: JSON.stringify({
        display_name: $("patientName").value.trim(),
      }),
    });
    event.target.reset();
    $("newPatientCard").classList.add("hidden");
    message("患者已建档，系统已自动生成患者编号");
    await loadPatients();
  } catch (error) {
    message(error.message, true);
  }
};

$("encounterForm").onsubmit = async (event) => {
  event.preventDefault();
  if (!selectedPatient) return;
  try {
    await api(`/patients/${selectedPatient.id}/encounters`, {
      method: "POST",
      body: JSON.stringify({
        display_label: $("encounterLabel").value.trim(),
        occurred_at: new Date($("occurredAt").value).toISOString(),
      }),
    });
    event.target.reset();
    $("encounterCard").classList.add("hidden");
    message("就诊已保存，系统已自动生成就诊编号");
    await loadPatients();
  } catch (error) {
    message(error.message, true);
  }
};

$("showNewPatient").onclick = () => $("newPatientCard").classList.remove("hidden");
$("createIntakeLink").onclick = createIntakeLink;
$("loadIntakes").onclick = loadIntakes;
$("closeIntakeLink").onclick = () => $("intakeLinkCard").classList.add("hidden");
$("revokeIntakeLink").onclick = async () => {
  if (!currentIntakeLinkId) return;
  try {
    await api(`/intake-links/${currentIntakeLinkId}/revoke`, { method: "POST" });
    $("intakeLinkCard").classList.add("hidden");
    message("通用建档二维码已撤销");
  } catch (error) {
    message(error.message, true);
  }
};
$("cancelNewPatient").onclick = () => $("newPatientCard").classList.add("hidden");
$("cancelEncounter").onclick = () => $("encounterCard").classList.add("hidden");
$("revokeInvite").onclick = async () => {
  if (!currentInvitationId) return;
  try {
    await api(`/invitations/${currentInvitationId}/revoke`, { method: "POST" });
    $("inviteCard").classList.add("hidden");
    message("邀请已撤销");
  } catch (error) {
    message(error.message, true);
  }
};
$("logout").onclick = () => {
  sessionStorage.removeItem("doctorToken");
  location.reload();
};
$("closeInvite").onclick = () => $("inviteCard").classList.add("hidden");

if (token) Promise.all([loadPatients(), loadCurrentNotice()]);
