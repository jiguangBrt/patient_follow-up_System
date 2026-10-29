(function () {
  "use strict";
  const forms = new WeakMap();
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
  let schemaPromise;
  async function schema() {
    if (!schemaPromise) schemaPromise = AppPaths.fetch("/gastritis/schema").then(async r => { if (!r.ok) throw new Error("量表加载失败，请重试"); return r.json(); }).catch(e => { schemaPromise = null; throw e; });
    return schemaPromise;
  }
  function select(options, value) {
    const n = el("select"); options.forEach(([key, label]) => { const o = el("option", label); o.value = key; n.append(o); }); n.value = value || options[0][0]; return n;
  }
  function summary(title, open = false) { const d = el("details", null, "gastritis-section"); d.open = open; d.append(el("summary", title)); return d; }
  async function render(container, payload = {}) {
    const data = await schema(); container.replaceChildren(); const state = { sections: {}, symptoms: {}, entries: {} }; forms.set(container, state);
    container.classList.add("gastritis-form");
    for (const section of data.sections) {
      const d = summary(section.label); d.dataset.section = section.key; const grid = el("div", null, "gastritis-grid"); state.sections[section.key] = {};
      for (const spec of section.fields) {
        const label = el(spec.kind === "checks" ? "div" : "label", spec.label); let control; const value = payload[section.key]?.[spec.key];
        if (spec.kind === "select") control = select(spec.options.map(x => [x, x]), value);
        else if (spec.kind === "checks") {
          control = el("div", null, "gastritis-checks"); spec.options.forEach(option => { const l = el("label"); const c = el("input"); c.type = "checkbox"; c.value = option; c.checked = Array.isArray(value) && value.includes(option); l.append(c, document.createTextNode(option)); control.append(l); });
        } else {
          control = el(spec.kind === "textarea" ? "textarea" : "input"); if (control.tagName === "INPUT") control.type = spec.kind === "date" ? "date" : spec.kind === "number" ? "number" : "text";
          control.value = value ?? ""; control.maxLength = 3000; if (spec.kind === "number") { control.min = spec.min; control.max = spec.max; control.step = "any"; }
          if (spec.kind === "date") control.max = new Date().toLocaleDateString("en-CA");
        }
        label.append(control); grid.append(label); state.sections[section.key][spec.key] = { control, spec, label };
      }
      d.append(grid); container.append(d);
      if (section.key === "basic") {
        const derived = el("output", null, "gastritis-derived"); d.append(derived); const calculate = () => {
          const basic = state.sections.basic; const birth = basic.date_of_birth.control.value; const h = Number(basic.height_cm.control.value); const w = Number(basic.weight_kg.control.value); let age = "待填写";
          if (birth) { const now = new Date(); const b = new Date(birth + "T00:00:00"); age = now.getFullYear() - b.getFullYear() - ((now.getMonth() < b.getMonth() || (now.getMonth() === b.getMonth() && now.getDate() < b.getDate())) ? 1 : 0); }
          derived.textContent = `年龄：${age}${typeof age === "number" ? "岁" : ""}　BMI：${h > 0 && w > 0 ? (w / (h / 100) ** 2).toFixed(1) : "待填写身高体重"}`;
        }; Object.values(state.sections.basic).forEach(({ control }) => control.addEventListener("input", calculate)); calculate();
      }
    }
    const symptoms = summary("症状"); symptoms.dataset.section = "symptoms"; const symptomsHint = el("p", "分级：1 偶有、程度较轻；2 时有、中等程度；3 经常、严重。", "muted"); symptoms.append(symptomsHint);
    Object.entries(data.symptoms).forEach(([key, label]) => {
      const raw = payload.symptoms?.[key] || {}; const row = el("div", null, "gastritis-symptom"); const name = el("label", label); const presence = select([["unknown", "未知/待确认"], ["no", "无"], ["yes", "有"]], raw.presence); name.append(presence);
      const gradeLabel = el("label", "程度"); const grade = select([["", "待填写"], ["1", "1 偶有、程度较轻"], ["2", "2 时有、中等程度"], ["3", "3 经常、严重"]], raw.grade == null ? "" : String(raw.grade)); gradeLabel.append(grade);
      const detailLabel = el("label", key === "weight_loss" ? "下降时间及体重（kg）" : key === "stomach_pain" ? "疼痛性质（隐痛/针扎/绞痛/灼痛/说不清）" : key === "poor_appetite" ? "没胃口、一吃就饱 / 饥饿但不敢多吃" : "补充情况（选填）"); const detail = el("input"); detail.type = "text"; detail.maxLength = 500; detail.value = raw.detail || ""; detailLabel.append(detail);
      const extras = {};
      const extraSpecs = key === "weight_loss" ? [["weight_loss_period", "体重下降时间", ["更长时间", "1年", "半年", "3个月内", "1个月内", "更短时间"]], ["weight_loss_kg", "下降体重（kg）"]] : key === "stomach_pain" ? [["pain_type", "疼痛性质", ["隐隐作痛", "针扎疼痛", "绞痛", "灼痛", "说不清"]]] : key === "poor_appetite" ? [["appetite_type", "食欲情况", ["没胃口、一吃就饱", "饥饿、但不敢多吃饭"]]] : [];
      extraSpecs.forEach(([extraKey, text, options]) => { const l = el("label", text); const c = options ? select([["", "待填写"], ...options.map(v => [v, v])], raw[extraKey]) : el("input"); if (!options) { c.type = "number"; c.min = "0.1"; c.max = "200"; c.step = "any"; c.value = raw[extraKey] ?? ""; } l.append(c); extras[extraKey] = { control: c, label: l }; });
      const toggle = () => { const active = presence.value === "yes"; gradeLabel.hidden = detailLabel.hidden = !active; grade.disabled = detail.disabled = !active; Object.values(extras).forEach(({ control, label }) => { label.hidden = !active; control.disabled = !active; }); }; presence.onchange = toggle; toggle(); row.append(name, gradeLabel, ...Object.values(extras).map(x => x.label), detailLabel); symptoms.append(row); state.symptoms[key] = { presence, grade, detail, extras };
    });
    const otherLabel = el("label", "其他症状及程度（选填）"); const other = el("textarea"); other.maxLength = 3000; other.value = payload.other_symptoms || ""; otherLabel.append(other); symptoms.append(otherLabel); state.other = other;
    container.insertBefore(symptoms, container.querySelector('[data-section="past_history"]'));
    const hp = state.sections.hp; const hpToggle = () => { const active = hp.infection.control.value !== "无"; ["count", "last_infection", "treated", "retest"].forEach(k => { hp[k].label.hidden = !active; hp[k].control.disabled = !active; }); }; hp.infection.control.onchange = hpToggle; hpToggle();
    const lifestyle = state.sections.lifestyle; const lifeToggle = () => {
      const smoke = lifestyle.smoking.control.value; const drink = lifestyle.drinking.control.value;
      ["cigarettes_per_day", "smoking_years", "quit_smoking_on"].forEach(k => { const active = ["既往吸烟", "当前吸烟"].includes(smoke) && (k !== "quit_smoking_on" || smoke === "既往吸烟"); lifestyle[k].label.hidden = !active; lifestyle[k].control.disabled = !active; });
      ["drinking_frequency", "alcohol_amount", "drinking_years", "quit_drinking_on"].forEach(k => { const active = ["近期戒酒", "偶尔", "经常"].includes(drink) && (k !== "quit_drinking_on" || drink === "近期戒酒"); lifestyle[k].label.hidden = !active; lifestyle[k].control.disabled = !active; });
    }; lifestyle.smoking.control.onchange = lifestyle.drinking.control.onchange = lifeToggle; lifeToggle();
    for (const [key, title] of [["diagnoses", "诊断记录"], ["medications", "治疗用药"], ["lab_results", "关键检验指标"]]) {
      const section = summary(title); section.dataset.section = key; const list = el("div"); state.entries[key] = [];
      const add = raw => { const row = el("div", null, "gastritis-entry"); const controls = {};
        for (const [k, label] of [["date", "日期"], ["name", "名称"], ["value", key === "medications" ? "剂量、疗程等" : "结果或补充"], ["source", "来源（报告/就诊/资料编号）"]]) { const l = el("label", label); const input = el("input"); input.type = k === "date" ? "date" : "text"; input.value = raw?.[k] || ""; input.maxLength = k === "source" ? 300 : k === "name" ? 200 : 500; l.append(input); row.append(l); controls[k] = input; }
        const remove = el("button", "删除本行", "secondary"); remove.type = "button"; const item = { controls, row }; remove.onclick = () => { state.entries[key] = state.entries[key].filter(x => x !== item); row.remove(); }; row.append(remove); list.append(row); state.entries[key].push(item);
      }; (payload[key] || []).forEach(add); const button = el("button", `＋ 添加${title}`, "secondary"); button.type = "button"; button.onclick = () => add(); section.append(list, button); container.append(section);
    }
    const groups = [["symptoms", "基本病情", ["symptoms"]], ["history", "既往病史", ["past_history", "hp"]], ["personal", "个人信息", ["basic", "lifestyle"]], ["clinical", "诊疗记录", ["diagnoses", "medications", "lab_results"]]];
    const sections = [...container.children]; const nav = el("div", null, "gastritis-tabs"); nav.setAttribute("role", "tablist"); nav.setAttribute("aria-label", "档案分类");
    const tabs = []; const panels = []; const prefix = container.id || "gastritis";
    function activate(index, expand = true) {
      tabs.forEach((tab, i) => { tab.setAttribute("aria-selected", String(i === index)); tab.tabIndex = i === index ? 0 : -1; panels[i].hidden = i !== index; });
      if (expand) { const first = panels[index].querySelector("details"); if (first) first.open = true; }
    }
    groups.forEach(([key, title, keys], index) => {
      const tab = el("button", title); tab.type = "button"; tab.id = `${prefix}-tab-${key}`; tab.setAttribute("role", "tab"); tab.setAttribute("aria-controls", `${prefix}-panel-${key}`);
      const panel = el("div", null, "gastritis-panel"); panel.id = `${prefix}-panel-${key}`; panel.setAttribute("role", "tabpanel"); panel.setAttribute("aria-labelledby", tab.id);
      sections.filter(section => keys.includes(section.dataset.section)).forEach(section => panel.append(section));
      tab.onclick = () => activate(index); tab.onkeydown = event => { const next = event.key === "ArrowRight" ? (index + 1) % groups.length : event.key === "ArrowLeft" ? (index + groups.length - 1) % groups.length : event.key === "Home" ? 0 : event.key === "End" ? groups.length - 1 : null; if (next != null) { event.preventDefault(); activate(next); tabs[next].focus(); } };
      tabs.push(tab); panels.push(panel); nav.append(tab);
    });
    container.replaceChildren(nav, ...panels); activate(0, false);
    container.querySelectorAll("input,select,textarea").forEach(control => control.addEventListener("invalid", () => { const index = panels.findIndex(panel => panel.contains(control)); if (index >= 0) activate(index); const section = control.closest("details"); if (section) section.open = true; }));
    return { read: () => read(container) };
  }
  function read(container) {
    const state = forms.get(container); if (!state) throw new Error("量表尚未加载"); const result = {};
    for (const [sectionKey, fields] of Object.entries(state.sections)) {
      result[sectionKey] = {}; for (const [key, { control, spec }] of Object.entries(fields)) {
        if (control.disabled) continue; let value;
        if (spec.kind === "checks") value = [...control.querySelectorAll("input:checked")].map(n => n.value);
        else if (spec.kind === "number") value = control.value === "" ? null : Number(control.value);
        else value = control.value; result[sectionKey][key] = value;
      }
    }
    result.symptoms = {}; for (const [key, { presence, grade, detail, extras }] of Object.entries(state.symptoms)) { result.symptoms[key] = { presence: presence.value, grade: presence.value === "yes" && grade.value ? Number(grade.value) : null, detail: presence.value === "yes" ? detail.value.trim() : "" }; if (presence.value === "yes") Object.entries(extras).forEach(([k, { control }]) => { if (control.value) result.symptoms[key][k] = k === "weight_loss_kg" ? Number(control.value) : control.value; }); }
    result.other_symptoms = state.other.value.trim();
    for (const [key, entries] of Object.entries(state.entries)) result[key] = entries.map(({ controls }) => Object.fromEntries(Object.entries(controls).map(([k, n]) => [k, n.value.trim()])));
    return result;
  }
  window.GastritisForms = { render, mount: render, read, schema };
  function initializeDoctor() {
    const button = document.getElementById("showGastritis"); if (!button) return;
    const dialog = document.getElementById("gastritisDialog"); const container = document.getElementById("gastritisFields"); const status = document.getElementById("gastritisMessage"); let patientId; let patientPermissions = []; let requestEpoch = 0;
    const request = async (path, options = {}) => { const response = await AppPaths.fetch(path, { ...options, headers: { "Content-Type": "application/json", Authorization: `Bearer ${AppPaths.storage.getItem(`${AppSession.staffRole()}Token`)}` } }); const data = await response.json(); if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "保存失败，请检查填写内容"); return data; };
    const report = (text, error = false) => { status.textContent = text; status.className = `status ${error ? "error" : "success"}`; };
    async function load() {
      const epoch = ++requestEpoch; const data = await request(`/patients/${patientId}/gastritis-records`); if (epoch !== requestEpoch || !dialog.open) return;
      const history = document.getElementById("gastritisHistory"); history.replaceChildren(); const option = el("option", "新记录（沿用最近填写内容）"); option.value = ""; history.append(option);
      data.records.forEach(record => { const o = el("option", `第${record.version}版 · ${record.recorded_on} · ${record.status === "confirmed" ? "已确认" : record.source === "patient" ? "患者自述待核对" : "医生草稿"}`); o.value = record.id; history.append(o); });
      const open = async record => { if (epoch !== requestEpoch) return; await render(container, record?.payload || data.initial_payload || {}); document.getElementById("gastritisDate").value = record?.recorded_on || new Date().toLocaleDateString("en-CA"); };
      history.onchange = () => open(data.records.find(r => String(r.id) === history.value)).catch(e => report(e.message, true)); await open(data.records[0]);
      document.getElementById("saveGastritisDraft").hidden = !patientPermissions.includes("edit"); document.getElementById("confirmGastritisRecord").hidden = !patientPermissions.includes("review"); document.getElementById("saveGastritisDraft").disabled = !patientPermissions.includes("edit"); document.getElementById("confirmGastritisRecord").disabled = !patientPermissions.includes("review");
    }
    button.onclick = async () => { patientId = button.dataset.patientId; if (!patientId) return; patientPermissions = (button.dataset.permissions || "").split(","); dialog.showModal(); report("正在加载…"); try { await load(); report(""); } catch (e) { report(e.message, true); } };
    document.getElementById("closeGastritis").onclick = () => dialog.close(); dialog.addEventListener("close", () => { requestEpoch++; });
    async function save(recordStatus) { const buttons = [document.getElementById("saveGastritisDraft"), document.getElementById("confirmGastritisRecord")]; buttons.forEach(b => b.disabled = true); try { await request(`/patients/${patientId}/gastritis-records`, { method: "POST", body: JSON.stringify({ recorded_on: document.getElementById("gastritisDate").value, payload: read(container), status: recordStatus }) }); await load(); report(recordStatus === "confirmed" ? "已确认并保存新版本" : "草稿已保存为新版本"); } catch (e) { report(e.message, true); } finally { buttons[0].disabled = !patientPermissions.includes("edit"); buttons[1].disabled = !patientPermissions.includes("review"); } }
    document.getElementById("saveGastritisDraft").onclick = () => save("draft"); document.getElementById("confirmGastritisRecord").onclick = () => save("confirmed");
  }
  initializeDoctor();
})();
