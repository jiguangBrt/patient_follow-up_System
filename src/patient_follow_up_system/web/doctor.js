const $ = (id) => document.getElementById(id);
let token = AppSession.require("doctor");
let currentInvitationId = null;
let currentIntakeLinkId = null;
let selectedPatient = null;
let doctorPatients = [];
let currentDoctorView = location.hash.slice(1) || "patients";

async function activateDoctorView() {
  if (!token || !document.body.classList.contains("signed-in")) return;
  const views = {
    patients: ["患者管理", "诊疗管理", "patientsCard"], intakes: ["建档申请", "诊疗管理", "intakesCard"],
    notice: ["患者须知", "设置", "noticeCard"], followups: ["随访计划", "随访与科研", "placeholderCard", "随访节点、复诊提醒与待补资料将在这里管理。"],
    cohorts: ["科研队列", "随访与科研", "placeholderCard", "患者筛选、队列纳入与研究分组将在这里管理。"],
    exports: ["资料导出", "随访与科研", "placeholderCard", "经授权的结构化资料与研究数据导出将在这里管理。"],
  };
  currentDoctorView = views[location.hash.slice(1)] ? location.hash.slice(1) : "patients";
  const [title, group, card, description] = views[currentDoctorView];
  ["patientsCard", "intakesCard", "noticeCard", "placeholderCard", "newPatientCard", "encounterCard", "inviteCard", "intakeLinkCard"].forEach(id => $(id).classList.add("hidden"));
  $(card).classList.remove("hidden");
  $("pageTitle").textContent = title; $("breadcrumb").textContent = `${group} / ${title}`;
  DoctorShell.activate(currentDoctorView);
  $("message").classList.add("hidden");
  if (description) { $("placeholderTitle").textContent = title; $("placeholderDescription").textContent = description; }
  if (currentDoctorView === "intakes") await loadIntakes();
}

function renderPatients() {
  const query = $("patientSearch").value.trim().toLowerCase();
  const items = doctorPatients.filter(p => `${p.display_name} ${p.patient_code}`.toLowerCase().includes(query));
  $("patientCounts").textContent = `共 ${doctorPatients.length} 位患者 · ${doctorPatients.filter(p => !p.is_bound).length} 位待认领`;
  $("patients").replaceChildren(...items.map(patientCard));
  if (!items.length) { const empty = document.createElement("p"); empty.className = "muted"; empty.textContent = query ? "没有匹配的患者。" : "暂无患者。可以新增患者，或从建档申请、病例审核中建立档案。"; $("patients").append(empty); }
}

function message(text, error = false) {
  $("message").textContent = text;
  $("message").className = `status ${error ? "error" : "success"}`;
}

async function api(path, options = {}) {
  options.headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const response = await AppPaths.fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    if (response.status === 401) {
      token = null; AppSession.logout("doctor", true);
    }
    throw new Error(typeof data?.detail === "string" ? data.detail : `请求失败（${response.status}）`);
  }
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
  const detailActions = document.createElement("div"); detailActions.className = "patient-detail-actions";
  detailActions.append(actionButton("新增就诊", () => openEncounterForm(patient), true), actionButton("查看 / 重印建档二维码", () => createInvite(patient.id)));
  details.prepend(detailActions);
  try {
    const [encounters, documents, clinicalRecords] = await Promise.all([
      api(`/patients/${patient.id}/encounters`),
      api(`/patients/${patient.id}/documents`),
      api(`/patients/${patient.id}/clinical-records`),
    ]);
    const clinicalHeading = document.createElement("h4");
    clinicalHeading.textContent = "结构化病历档案（医生已确认）";
    const intakeHistory = await api(`/patients/${patient.id}/intake-submissions`);
    if (intakeHistory.length) {
      const latest = intakeHistory[0];
      details.append(detailLine("患者基本信息", `${latest.sex} · 生日 ${latest.date_of_birth} · 操作员 ${latest.operator_relationship}`));
      details.append(detailLine("患者须知", `${latest.notice_version} · ${new Date(latest.consented_at).toLocaleString()}`));
      intakeHistory.forEach(row => {
        if (!row.has_document) return;
        const upload = document.createElement("div"); upload.className="timeline-item";
        upload.append(detailLine("扫码补交资料", new Date(row.created_at).toLocaleString()), actionButton("查看原件", () => openIntakeDocument(row.id), true), actionButton("识别并逐字段审核", () => {location.href = AppPaths.url(`/clinical?source=intake&id=${row.id}`);}, true));
        details.append(upload);
      });
    }
    details.append(clinicalHeading);
    if (!clinicalRecords.length) details.append(detailLine("病历记录", "暂无已确认入档内容"));
    clinicalRecords.forEach(record => {
      const item = document.createElement("article"); item.className = "timeline-item approved";
      item.append(detailLine("原件", record.original_name), detailLine("审核版本", `${record.version} · ${record.pending_fields} 项仍待确认`));
      record.fields.forEach(field => item.append(detailLine(field.label, field.confirmed_value)));
      item.append(actionButton("查看原件、证据与审核记录", () => { location.href = AppPaths.url(`/clinical?id=${record.id}`); }, true));
      details.append(item);
    });
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
        item.append(text, actionButton("查看患者建档二维码", () => createInvite(patient.id, encounter.id), true));
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
    detailLine("资料处理", "原件已保存，可从下方入口查看识别与逐字段审核结果"),
    detailLine("须知记录", `${record.notice_version} · ${new Date(record.consented_at).toLocaleString()}`),
  );
  item.append(actionButton("查看原始资料", () => openPatientDocument(record.id), true));
  item.append(actionButton("提取候选与逐字段审核", () => { location.href = AppPaths.url(`/clinical?source=patient&id=${record.id}`); }, true));
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
  const response = await AppPaths.fetch(`/patient-documents/${documentId}/file`, { headers: { Authorization: `Bearer ${token}` } });
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
  badge.textContent = "患者专属档案";
  badge.title = "请通过专属建档二维码填写基本信息";
  text.append(name, code);
  const actions = document.createElement("div");
  actions.className = "row patient-actions";
  const details = document.createElement("div");
  details.className = "patient-details hidden";
  actions.append(
    actionButton("查看档案 →", () => showPatientDetails(patient, details), true),
    actionButton("建档二维码 / 重印", () => createInvite(patient.id)),
  );
  const binding = document.createElement("div"); binding.append(badge);
  summary.append(text, binding, actions);
  card.append(summary, details);
  return card;
}

async function loadPatients() {
  try {
    const me = await api("/auth/me");
    if (me.role !== "doctor") { AppSession.logout("doctor"); return; }
    DoctorShell.setUser(me.display_name);
    const items = await api("/patients");
    document.body.classList.add("signed-in");
    doctorPatients = items;
    renderPatients();
  } catch (error) {
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
    const data = await api(`/patients/${patientId}/intake-link`, {method:"POST"});
    currentInvitationId = data.id;
    $("qr").innerHTML = data.qr_svg;
    $("qrPatientName").textContent = data.display_name;
    $("openInvite").href = data.intake_url;
    $("qrUrl").textContent = data.intake_url;
    const revoked = data.state !== "available";
    $("expiry").textContent = revoked ? "此码已停用，患者无法继续使用。" : "长期有效 · 可重复扫码 · 无需核验码";
    $("printInvite").disabled = revoked;
    $("revokeInvite").disabled = revoked;
    $("openInvite").classList.toggle("hidden", revoked);
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
    message(action === "approve" ? "已批准，可在患者档案中查看" : "申请已驳回");
    await loadIntakes();
    await loadPatients();
  } catch (error) {
    message(error.message, true);
  }
}

async function openIntakeDocument(submissionId) {
  const response = await AppPaths.fetch(`/intake-submissions/${submissionId}/document`, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) {
    if (response.status === 401) { AppSession.logout("doctor", true); return; }
    const error = await response.json().catch(() => ({}));
    message(typeof error.detail === "string" ? error.detail : "原始资料暂时无法打开", true); return;
  }
  const url = URL.createObjectURL(await response.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

async function loadIntakes() {
  try {
    const items = await api("/intake-submissions");
    $("intakes").replaceChildren(...items.map((submission) => {
      const item = document.createElement("article");
      item.className = "patient-card-wide";
      item.append(
        detailLine("患者姓名", submission.display_name),
        detailLine("基本信息", `${submission.sex} · ${submission.date_of_birth} · ${submission.operator_relationship}`),
        detailLine("状态", {pending:"等待医生审核",approved:"已批准",rejected:"已驳回"}[submission.status] || submission.status),
        detailLine("演示同意", submission.consented_at ? `${submission.notice_version} · ${new Date(submission.consented_at).toLocaleString()}${submission.consent_is_legacy_incomplete ? " · 历史内容快照不完整" : ""}` : "未记录"),
        detailLine("资料处理", !submission.has_document ? "仅提交基本信息，未上传病历文件" : submission.extraction_status === "pending" ? "原件已保存，待提取/审核" : submission.extraction_status),
      );
      const actionBar = document.createElement("div");actionBar.className="intake-action-bar";
      if (submission.has_document) {
        const documents = document.createElement("div");documents.className="intake-document-actions";
        documents.append(actionButton("查看原始资料", () => openIntakeDocument(submission.id), true), actionButton("识别并逐字段审核", () => { location.href = AppPaths.url(`/clinical?source=intake&id=${submission.id}`); }, true));
        actionBar.append(documents);
      }
      if (submission.status === "pending") {
        const actions = document.createElement("div");
        actions.className = "intake-review-actions";
        const reject = actionButton("驳回", () => reviewIntake(submission, "reject"));reject.className="danger";
        actions.append(
          actionButton("批准", () => reviewIntake(submission, "approve")),
          reject,
        );
        actionBar.append(actions);
      }
      if(actionBar.childElementCount)item.append(actionBar);
      return item;
    }));
    if (!items.length) $("intakes").textContent = "暂无建档申请。请在患者管理中先录入姓名，再生成患者专属建档码。";
  } catch (error) {
    message(error.message, true);
  }
}

async function loadCurrentNotice() {
  try {
    const notice = await api("/doctor/patient-notices/current");
    $("doctorNoticeSummary").textContent = `${notice.title} · 版本 ${notice.version} · 已发布并生效`;
    $("doctorNoticeContent").textContent = notice.content;
  } catch (error) { message(error.message, true); }
}

$("newPatientForm").onsubmit = async (event) => {
  event.preventDefault();
  try {
    const patient = await api("/patients", {
      method: "POST",
      body: JSON.stringify({
        display_name: $("patientName").value.trim(),
      }),
    });
    event.target.reset();
    $("newPatientCard").classList.add("hidden");
    message("已保存医生设定的姓名，可打印专属建档二维码");
    await loadPatients();
    await createInvite(patient.id);
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

$("showNewPatient").onclick = () => { $("newPatientCard").classList.remove("hidden"); $("newPatientCard").scrollIntoView({behavior:"smooth",block:"start"}); };
$("createIntakeLink").onclick = () => {location.hash="patients"; message("请点击新增患者，录入姓名后生成专属码。");};
$("refreshIntakes").onclick = loadIntakes;
$("patientSearch").oninput = renderPatients;
window.addEventListener("hashchange", activateDoctorView);
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
    await api(`/intake-links/${currentInvitationId}/revoke`, { method: "POST" });
    $("inviteCard").classList.add("hidden");
    message("患者建档二维码已停用，已打印的二维码也无法继续使用");
  } catch (error) {
    message(error.message, true);
  }
};
$("logout").onclick = () => {
  AppSession.logout("doctor");
};
$("printInvite").onclick = () => window.print();
$("closeInvite").onclick = () => $("inviteCard").classList.add("hidden");

if (token) Promise.all([loadPatients(), loadCurrentNotice()]).then(activateDoctorView);
