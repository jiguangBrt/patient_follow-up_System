(() => {
  const STORAGE_KEY = "doctorTour";
  const API_PATH = "/onboarding/doctor-tour";
  const STEPS = [
    { page:"/doctor", view:"patients", target:'[data-view="patients"]', interactive:true,
      title:"患者管理",
      body:"这里管理您负责的全部患者：左侧是患者名单与搜索，右侧按就诊日期展示档案。引导只带您浏览入口，不会替您建档、提交或审核。" },
    { page:"/doctor", view:"patients", target:"#showNewPatient",
      title:"新增患者与建档二维码",
      body:"点击“＋ 新增患者”录入姓名并保存，即可在档案顶部生成该患者的专属建档二维码。患者扫码后阅读须知、填写基本信息并补交病历。" },
    { page:"/doctor", view:"intakes", target:'[data-view="intakes"]', interactive:true,
      title:"建档申请",
      body:"患者扫码提交的信息会进入“建档申请”列表。在这里核对姓名、性别、出生日期与提交资料，然后批准或驳回。" },
    { page:"/clinical", view:"clinical", target:'[data-view="clinical"]', interactive:true,
      title:"病例识别与审核",
      body:"这是病例识别与审核工作区。胃镜、病理等原件上传后先进入缓冲区，不会自动绑定任何患者或账号。" },
    { page:"/clinical", view:"clinical", target:"#uploadCard", fallback:"#bufferCard",
      title:"上传原件与逐字段审核",
      body:"支持 JPG、PNG、PDF（8 MB 以内）。上传后可运行本机 OCR 提取候选字段，所有内容经您逐字段确认后才归入患者档案。" },
    { page:"/doctor", view:"notice", target:'[data-view="notice"]', interactive:true,
      title:"患者须知",
      body:"这里展示当前生效的患者须知版本与正文。患者扫码建档时阅读并同意的就是同一版本。" },
    { page:"/doctor", view:"followups", target:'[data-view="followups"]', interactive:true,
      title:"随访与科研（待建设）",
      body:"“随访计划”的节点提醒、缺失资料补录正在建设中；同组的“科研队列”“资料导出”也尚未开放，上线前会以“待建设”标注。" },
  ];

  const page = () => AppPaths.pathname();
  const view = () => page() === "/clinical" ? "clinical" : location.hash.slice(1) || "patients";
  const readState = () => {
    try { const raw = AppPaths.storage.getItem(STORAGE_KEY); return raw ? JSON.parse(raw) : null; }
    catch { return null; }
  };
  const writeState = state => AppPaths.storage.setItem(STORAGE_KEY, JSON.stringify(state));
  const clearState = () => AppPaths.storage.removeItem(STORAGE_KEY);
  const token = () => AppPaths.storage.getItem("doctorToken");

  let active = null;
  let nodes = null;
  let repositionQueued = false;

  function persist(action) {
    const auth = token();
    if (!auth) return;
    AppPaths.fetch(API_PATH, {
      method:"POST",
      headers:{"Content-Type":"application/json", Authorization:`Bearer ${auth}`},
      body:JSON.stringify({action}),
    }).catch(()=>{});
  }

  function stepFor(locationPage, locationView) {
    return STEPS.findIndex(step => step.page === locationPage && (!step.view || step.view === locationView));
  }

  function build() {
    const overlay = document.createElement("div"); overlay.className = "tour-overlay";
    const spotlight = document.createElement("div"); spotlight.className = "tour-spotlight";
    const card = document.createElement("div"); card.className = "tour-card"; card.setAttribute("role","dialog"); card.setAttribute("aria-live","polite");
    document.body.append(overlay, spotlight, card);
    nodes = { overlay, spotlight, card };
    window.addEventListener("resize", scheduleReposition);
    document.addEventListener("scroll", scheduleReposition, true);
    document.addEventListener("keydown", onKeydown);
  }

  function teardown() {
    if (nodes) { nodes.overlay.remove(); nodes.spotlight.remove(); nodes.card.remove(); nodes = null; }
    window.removeEventListener("resize", scheduleReposition);
    document.removeEventListener("scroll", scheduleReposition, true);
    document.removeEventListener("keydown", onKeydown);
  }

  function onKeydown(event) {
    if (event.key === "Escape" && active) { event.preventDefault(); exit(); }
  }

  function scheduleReposition() {
    if (repositionQueued) return;
    repositionQueued = true;
    requestAnimationFrame(() => { repositionQueued = false; if (active && nodes) place(active.step); });
  }

  function findTarget(step) {
    for (const selector of [step.target, step.fallback].filter(Boolean)) {
      const el = document.querySelector(selector);
      if (el) {
        // 目标可能藏在可滚动区域（如侧边栏导航）内，先滚动到可见再测量。
        el.scrollIntoView({ block: "nearest" });
        const rect = el.getBoundingClientRect();
        if (rect.width && rect.height) return rect;
      }
    }
    return null;
  }

  function holePolygon(rect) {
    const pad = 8;
    const x1 = Math.max(0, rect.left - pad), y1 = Math.max(0, rect.top - pad);
    const x2 = Math.min(window.innerWidth, rect.right + pad), y2 = Math.min(window.innerHeight, rect.bottom + pad);
    return `polygon(evenodd, 0 0, 100% 0, 100% 100%, 0 100%, 0 0, ${x1}px ${y1}px, ${x2}px ${y1}px, ${x2}px ${y2}px, ${x1}px ${y2}px, ${x1}px ${y1}px)`;
  }

  function place(index) {
    const step = STEPS[index];
    const rect = findTarget(step);
    const { overlay, spotlight, card } = nodes;
    const interactive = Boolean(step.interactive && rect);
    overlay.style.clipPath = rect && interactive ? holePolygon(rect) : "none";
    if (rect) {
      spotlight.style.display = "";
      spotlight.style.top = `${rect.top - 8}px`;
      spotlight.style.left = `${rect.left - 8}px`;
      spotlight.style.width = `${rect.width + 16}px`;
      spotlight.style.height = `${rect.height + 16}px`;
    } else {
      spotlight.style.display = "none";
    }
    card.classList.toggle("tour-centered", !rect);
    if (rect) {
      card.style.transform = "";
      const cardHeight = card.offsetHeight || 200;
      const cardWidth = card.offsetWidth || 360;
      let top = rect.bottom + 18;
      if (top + cardHeight > window.innerHeight - 12) top = Math.max(12, rect.top - cardHeight - 18);
      let left = Math.min(Math.max(12, rect.left), window.innerWidth - cardWidth - 12);
      card.style.top = `${top}px`;
      card.style.left = `${left}px`;
    }
  }

  function render(index) {
    if (!nodes) build();
    const step = STEPS[index];
    const total = STEPS.length;
    const last = index === total - 1;
    nodes.card.innerHTML = `
      <button type="button" class="tour-close" aria-label="关闭引导">✕</button>
      <h2></h2><p></p>
      <div class="tour-progress"><span class="tour-progress-text">第 ${index + 1} 步 · 共 ${total} 步</span><div class="tour-progress-track"><div class="tour-progress-bar" style="width:${((index + 1) / total) * 100}%"></div></div></div>
      <div class="tour-actions">
        ${index > 0 ? '<button type="button" class="secondary tour-prev">上一步</button>' : ""}
        <button type="button" class="tour-next">${last ? "完成" : "下一步"}</button>
        <button type="button" class="tour-skip">跳过引导</button>
      </div>`;
    nodes.card.querySelector("h2").textContent = step.title;
    nodes.card.querySelector("p").textContent = step.body;
    nodes.card.querySelector(".tour-close").onclick = exit;
    nodes.card.querySelector(".tour-skip").onclick = exit;
    nodes.card.querySelector(".tour-next").onclick = () => (last ? finish() : go(index + 1));
    const prev = nodes.card.querySelector(".tour-prev");
    if (prev) prev.onclick = () => go(index - 1);
    place(index);
    [320, 900].forEach(delay => setTimeout(() => { if (active && nodes) place(active.step); }, delay));
  }

  function renderWelcome(onStart, onLater) {
    if (!nodes) build();
    nodes.overlay.style.clipPath = "none";
    nodes.spotlight.style.display = "none";
    nodes.card.classList.add("tour-centered");
    nodes.card.innerHTML = `
      <button type="button" class="tour-close" aria-label="关闭">✕</button>
      <h2>欢迎使用随访工作台</h2>
      <p>花一分钟了解患者管理、建档申请、病例识别与审核和患者须知的用途与入口；随访、科研等模块目前标注为“待建设”。</p>
      <div class="tour-actions">
        <button type="button" class="tour-welcome-start">开始引导</button>
        <button type="button" class="tour-skip">暂不</button>
      </div>`;
    nodes.card.querySelector(".tour-welcome-start").onclick = onStart;
    nodes.card.querySelector(".tour-skip").onclick = onLater;
    nodes.card.querySelector(".tour-close").onclick = onLater;
  }

  function go(index) {
    const step = STEPS[index];
    active = { ...active, step: index };
    writeState(active);
    if (step.page !== page() || (step.view && step.view !== view())) {
      const link = document.querySelector(`[data-view="${step.view || (step.page === "/clinical" ? "clinical" : "")}"]`);
      if (link) { link.click(); return; }
      location.href = AppPaths.url(step.page === "/clinical" ? "/clinical" : `/doctor#${step.view}`);
      return;
    }
    render(index);
  }

  function resumeHere() {
    const state = active || readState();
    if (!state || !STEPS[state.step]) return false;
    let index = state.step;
    if (STEPS[index].page !== page()) {
      // 浏览器前进/后退把用户带到了不属于当前步骤的页面，跟随到本页对应步骤。
      const match = stepFor(page(), view());
      if (match >= 0) index = match;
    }
    active = { ...state, step: index };
    writeState(active);
    render(index);
    return true;
  }

  function finish() {
    const replay = active?.replay;
    teardown(); active = null; clearState();
    if (!replay) persist("complete");
  }

  function exit() {
    const replay = active?.replay;
    teardown(); active = null; clearState();
    if (!replay) persist("skip");
  }

  window.addEventListener("hashchange", () => {
    if (active) resumeHere();
  });

  window.DoctorTour = {
    start(replay = true) {
      active = { step: 0, replay };
      writeState(active);
      go(0);
    },
    resumeIfActive() {
      if (AppSession.staffRole?.() !== "doctor") return;
      if (readState()) resumeHere();
    },
    async maybePrompt(user) {
      if (readState() || page() !== "/doctor" || user?.role !== "doctor") return;
      const auth = token();
      if (!auth) return;
      try {
        const response = await AppPaths.fetch(API_PATH, { headers:{ Authorization:`Bearer ${auth}` } });
        if (!response.ok) return;
        const status = (await response.json()).status;
        if (status !== "pending" || readState()) return;
        active = { step: 0, replay: false };
        renderWelcome(
          () => { writeState(active); go(0); },
          () => exit(),
        );
      } catch { /* 引导状态不可用时不影响工作台 */ }
    },
  };
})();
