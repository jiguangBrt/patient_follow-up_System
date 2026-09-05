const $ = (id) => document.getElementById(id);
let intakeToken = new URLSearchParams(location.hash.slice(1)).get("token") || sessionStorage.getItem("intakeToken");
let submissionKey = sessionStorage.getItem("intakeSubmissionKey");
if (!submissionKey) { const bytes = new Uint8Array(24); crypto.getRandomValues(bytes); submissionKey = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join(""); sessionStorage.setItem("intakeSubmissionKey", submissionKey); }
if (intakeToken) { sessionStorage.setItem("intakeToken", intakeToken); history.replaceState(null, "", location.pathname); }
async function request(path, body) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await response.json(); if (!response.ok) throw new Error(data.detail || "请求失败"); return data;
}
async function check() {
  if (!intakeToken) { $("status").textContent = "二维码不可用，请联系医护人员"; $("status").classList.add("error"); return; }
  try { const data = await request("/intake-links/status", { intake_token: intakeToken }); if (data.state !== "available") throw new Error(); $("status").textContent = "二维码有效，可以填写"; $("status").classList.add("success"); $("intakeForm").classList.remove("hidden"); }
  catch { $("status").textContent = "二维码已失效，请联系医护人员"; $("status").classList.add("error"); }
}
$("intakeForm").onsubmit = async (event) => {
  event.preventDefault(); $("submitButton").disabled = true;
  try {
    const file = $("document").files[0]; if (!file || file.size > 8 * 1024 * 1024) throw new Error("请选择不超过 8 MB 的资料");
    const bytes = new Uint8Array(await file.arrayBuffer()); let binary = ""; bytes.forEach(byte => { binary += String.fromCharCode(byte); });
    await request("/intake-submissions", { intake_token: intakeToken, submission_key: submissionKey, display_name: $("displayName").value.trim(), sex: $("sex").value, date_of_birth: $("dateOfBirth").value, operator_relationship: $("relationship").value, notice_version: "demo-notice-v1", consent_given: $("consent").checked, document_name: file.name, document_mime_type: file.type, document_base64: btoa(binary) });
    $("intakeForm").classList.add("hidden"); $("done").classList.remove("hidden"); $("status").textContent = "提交成功"; $("status").className = "status success"; sessionStorage.removeItem("intakeToken");
  } catch (error) { $("status").textContent = error.message || "提交失败，请检查信息或联系医护人员"; $("status").className = "status error"; $("status").scrollIntoView({ behavior: "smooth", block: "center" }); $("submitButton").disabled = false; }
};
$("document").onchange = () => { const file = $("document").files[0]; if (file && file.type.startsWith("image/")) { $("preview").src = URL.createObjectURL(file); $("preview").classList.remove("hidden"); } else { $("preview").classList.add("hidden"); } };
check();
