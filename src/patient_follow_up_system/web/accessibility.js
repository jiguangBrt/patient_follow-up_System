(() => {
  const storageKey = "patient-follow-up-large-text";
  const root = document.documentElement;

  const readPreference = () => {
    try {
      return localStorage.getItem(storageKey) === "true";
    } catch {
      return false;
    }
  };

  const applyPreference = (enabled) => {
    root.classList.toggle("large-text", enabled);
    document.querySelectorAll(".text-size-toggle").forEach((button) => {
      button.setAttribute("aria-pressed", String(enabled));
      button.textContent = `大字模式：${enabled ? "开" : "关"}`;
      button.title = enabled ? "切换为标准字号" : "切换为大字模式";
    });
  };

  applyPreference(readPreference());

  const addControl = () => {
    if (document.querySelector(".text-size-toggle")) return;
    const dock = document.createElement("div");
    dock.className = "accessibility-dock";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "text-size-toggle";
    button.setAttribute("aria-label", "切换大字模式");
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => {
      const enabled = !root.classList.contains("large-text");
      try {
        localStorage.setItem(storageKey, String(enabled));
      } catch {
      }
      applyPreference(enabled);
    });
    dock.appendChild(button);

    const doctorMain = document.querySelector(".doctor-main");
    const brandBar = document.querySelector(".brand-bar");
    const patientHeader = document.querySelector(".patient-header");
    if (doctorMain) doctorMain.prepend(dock);
    else if (brandBar) brandBar.appendChild(dock);
    else if (patientHeader) patientHeader.appendChild(dock);
    else document.body.prepend(dock);
    applyPreference(readPreference());
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", addControl, { once: true });
  } else {
    addControl();
  }

  window.addEventListener("storage", (event) => {
    if (event.key === storageKey || event.key === null) applyPreference(readPreference());
  });
})();
