(() => {
  "use strict";
  const $ = id => document.getElementById(id);

  const defaultWards = [
    { id: "emergency", name: "Emergency & Trauma", total: 20, free: 6, status: "Active" },
    { id: "general", name: "General Medicine", total: 50, free: 18, status: "Active" },
    { id: "icu", name: "Intensive Care (ICU)", total: 15, free: 3, status: "Active" },
    { id: "paediatrics", name: "Paediatrics Ward", total: 25, free: 11, status: "Active" }
  ];

  let wards = structuredClone(defaultWards);
  let auditLogs = [
    { time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), action: "SYSTEM_BOOT", ward: "4 Wards Online", actor: "ops.admin@flowmed-nexus.demo" }
  ];

  const titles = {
    dashboard: "Dashboard overview",
    patients: "Patient triage & directory",
    appointments: "Appointment schedule",
    beds: "Smart bed management",
    labs: "Diagnostic lab pipeline",
    assistant: "AI operations copilot",
    account: "Workspace & access",
    admin: "Admin control centre"
  };

  function sanitizeText(val) {
    return String(val ?? "").replace(/[<>\"'`;]/g, "").trim();
  }

  function showPage(page) {
    document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
    const target = $("page-" + page);
    if (!target) return;
    target.classList.add("active");
    document.querySelectorAll(".nav button").forEach(b => {
      const active = b.dataset.page === page;
      b.classList.toggle("active", active);
      if (active) b.setAttribute("aria-current", "page");
      else b.removeAttribute("aria-current");
    });
    $("pageTitle").textContent = titles[page] || "FlowMed Nexus 2.0";
  }

  function filterTable(inputId, rowsId) {
    const term = $(inputId).value.toLowerCase();
    for (const row of $(rowsId).rows) {
      row.style.display = row.innerText.toLowerCase().includes(term) ? "" : "none";
    }
  }

  function computeCapacityMetrics(wardList) {
    const total = wardList.reduce((s, w) => s + w.total, 0);
    const free = wardList.reduce((s, w) => s + w.free, 0);
    const occupancy = total ? Math.round((total - free) / total * 100) : 0;
    const sorted = [...wardList].sort((a, b) => (a.free / a.total) - (b.free / b.total));
    return { total, free, occupancy, busiest: sorted[0] || null, openest: sorted[sorted.length - 1] || null };
  }

  function askAI() {
    const q = sanitizeText($("question").value);
    const replyEl = $("reply");
    if (!q) {
      replyEl.textContent = "Enter an operational question above to run AI capacity analysis.";
      return;
    }

    const lower = q.toLowerCase();
    const { total, free, occupancy, busiest, openest } = computeCapacityMetrics(wards);
    const busiestOcc = busiest ? Math.round((busiest.total - busiest.free) / busiest.total * 100) : 0;
    const transferCount = busiest && openest ? Math.min(3, Math.floor(openest.free / 2)) : 0;

    if (lower.includes("handoff") || lower.includes("shift")) {
      replyEl.textContent = [
        `✧ Shift Handoff Executive Summary (${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}):`,
        `• Active Census: ${total - free} admitted patients across ${wards.length} wards (${occupancy}% load).`,
        `• Critical Watchlist: ${busiest ? busiest.name : "ICU"} at ${busiestOcc}% occupancy—prioritize step-down evaluation.`,
        `• Incoming Shift Action: Pre-allocate ${transferCount} buffer beds in ${openest ? openest.name : "General Medicine"} before next ward rounds.`
      ].join("\n");
      return;
    }

    if (lower.includes("surge") || lower.includes("reallocation")) {
      replyEl.textContent = [
        "⚡ Autonomous ER Surge Reallocation Plan:",
        `• Immediate Buffer: ${free} total open beds detected across hospital network.`,
        `• Step 1 (Triage Diversion): Route low-acuity Priority 2 cases directly to ${openest ? openest.name : "General Medicine"} (${openest ? openest.free : 0} beds free).`,
        `• Step 2 (Step-Down Transfer): Transfer ${transferCount} stable patients out of ${busiest ? busiest.name : "ICU"} (${busiestOcc}% full) to unlock acute trauma slots.`
      ].join("\n");
      return;
    }

    replyEl.textContent = [
      `✧ FlowMed AI Capacity Recommendation for "${q}":`,
      `• Network Capacity: ${free} of ${total} total beds available (${occupancy}% hospital occupancy).`,
      `• Primary Bottleneck: ${busiest ? busiest.name : "N/A"} is at ${busiestOcc}% occupancy (${busiest ? busiest.free : 0} beds left).`,
      `• Actionable Routing: Route non-critical step-down patients to ${openest ? openest.name : "General Ward"} (${openest ? openest.free : 0} beds open) to preserve critical care buffer.`
    ].join("\n");
  }

  function simulateSurge() {
    let remaining = 6;
    for (const w of wards) {
      if (remaining > 0 && w.free > 0) {
        const take = Math.min(w.free, remaining, 2);
        w.free -= take;
        remaining -= take;
      }
    }
    addAudit("ER_SURGE_SIMULATED", "Multi-Ward (+6 Admissions)");
    renderAll();
    $("aiLiveBanner").textContent = "⚡ Surge Alert Active: 6 emergency admissions routed across wards. AI recommends preparing discharge-ready patients in General Medicine.";
  }

  function safeText(tag, value) {
    const el = document.createElement(tag);
    el.textContent = String(value ?? "");
    return el;
  }

  function adjustBed(id, delta) {
    const w = wards.find(x => x.id === id);
    if (!w) return;
    const nextFree = w.free + delta;
    if (nextFree < 0 || nextFree > w.total) return;
    w.free = nextFree;
    addAudit(delta < 0 ? "PATIENT_ADMITTED" : "PATIENT_DISCHARGED", w.name);
    renderAll();
  }

  function renderAll() {
    const grid = $("wardGrid");
    const adminBody = $("adminWardRows");
    const gridFrag = document.createDocumentFragment();
    const adminFrag = document.createDocumentFragment();
    const colors = ["mint", "lav", "yellow", "peach"];

    wards.forEach((w, index) => {
      const occPct = w.total ? Math.round((w.total - w.free) / w.total * 100) : 0;

      const card = document.createElement("article");
      card.className = "card bed-card";
      card.setAttribute("aria-label", `${w.name} bed status`);

      const top = document.createElement("div");
      top.className = "bed-top";
      const icon = safeText("span", "▤");
      icon.className = "stat-icon " + colors[index % colors.length];
      icon.setAttribute("aria-hidden", "true");
      const badge = safeText("span", occPct >= 85 ? "Critical" : occPct >= 70 ? "High" : "Optimal");
      badge.className = "badge" + (occPct >= 85 ? " badge-crit" : occPct >= 70 ? " badge-warn" : "");
      top.append(icon, badge);

      const heading = safeText("h3", w.name);
      const number = safeText("div", `${w.free} / ${w.total}`);
      number.className = "bed-number";
      const label = safeText("p", `Available beds (${occPct}% occupied)`);

      const bar = document.createElement("div");
      bar.className = "bar";
      bar.setAttribute("role", "progressbar");
      bar.setAttribute("aria-label", `${w.name} occupancy`);
      bar.setAttribute("aria-valuenow", String(occPct));
      bar.setAttribute("aria-valuemin", "0");
      bar.setAttribute("aria-valuemax", "100");
      const fill = document.createElement("span");
      fill.style.width = occPct + "%";
      if (occPct >= 85) fill.className = "crit";
      else if (occPct >= 70) fill.className = "warn";
      bar.appendChild(fill);

      const controls = document.createElement("div");
      controls.className = "bed-controls";
      const admitBtn = safeText("button", "+ Admit");
      admitBtn.type = "button";
      admitBtn.className = "btn btn-soft btn-xs";
      admitBtn.setAttribute("aria-label", `Admit patient to ${w.name}`);
      admitBtn.disabled = w.free === 0;
      admitBtn.addEventListener("click", () => adjustBed(w.id, -1));

      const dischargeBtn = safeText("button", "- Discharge");
      dischargeBtn.type = "button";
      dischargeBtn.className = "btn btn-soft btn-xs";
      dischargeBtn.setAttribute("aria-label", `Discharge patient from ${w.name}`);
      dischargeBtn.disabled = w.free === w.total;
      dischargeBtn.addEventListener("click", () => adjustBed(w.id, 1));

      controls.append(admitBtn, dischargeBtn);
      card.append(top, heading, number, label, bar, controls);
      gridFrag.appendChild(card);

      const tr = document.createElement("tr");
      [w.name, w.total, w.free, w.status].forEach(v => tr.appendChild(safeText("td", v)));
      const actions = document.createElement("td");
      const edit = safeText("button", "Edit");
      const del = safeText("button", "Delete");
      edit.type = "button";
      del.type = "button";
      edit.className = "btn btn-soft btn-xs";
      edit.setAttribute("aria-label", `Edit ${w.name}`);
      del.className = "btn btn-danger btn-xs ml-5";
      del.setAttribute("aria-label", `Delete ${w.name}`);
      edit.addEventListener("click", () => editWard(w.id));
      del.addEventListener("click", () => removeWard(w.id));
      actions.append(edit, del);
      tr.appendChild(actions);
      adminFrag.appendChild(tr);
    });

    grid.replaceChildren(gridFrag);
    adminBody.replaceChildren(adminFrag);

    const { total, free, occupancy } = computeCapacityMetrics(wards);
    $("dashboardBeds").textContent = String(free);
    $("navBedPill").textContent = String(free);
    $("bedAvailabilityBadge").textContent = total ? Math.round(free / total * 100) + "% free" : "No data";
    $("dashboardBedFoot").textContent = total ? `${free} of ${total} beds open` : "No ward records";
    $("dashboardOccupancy").textContent = total ? occupancy + "%" : "—";
    $("dashboardOccupancyBar").style.width = occupancy + "%";
    $("dashboardOccupancyRole").setAttribute("aria-valuenow", String(occupancy));
    $("occStatusBadge").textContent = occupancy >= 80 ? "High Load" : "Balanced";
    $("wardNote").textContent = `Live Telemetry: ${free} of ${total} beds available across ${wards.length} wards (${occupancy}% hospital-wide occupancy).`;

    const auditFrag = document.createDocumentFragment();
    for (const log of auditLogs) {
      const tr = document.createElement("tr");
      [log.time, log.action, log.ward, log.actor].forEach(v => tr.appendChild(safeText("td", v)));
      auditFrag.appendChild(tr);
    }
    $("auditRows").replaceChildren(auditFrag);
  }

  function addAudit(action, wardName) {
    const actor = $("userStatus").textContent || "ops.admin@flowmed-nexus.demo";
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    auditLogs.unshift({ time, action, ward: wardName, actor });
    if (auditLogs.length > 200) auditLogs.pop();
  }

  function clearWardForm(keepMessage = false) {
    $("wardEditId").value = "";
    $("wardName").value = "";
    $("totalBeds").value = "";
    $("availableBeds").value = "";
    $("wardStatus").value = "Active";
    if (!keepMessage) $("adminMessage").textContent = "";
  }

  function editWard(id) {
    const w = wards.find(x => x.id === id);
    if (!w) return;
    $("wardEditId").value = w.id;
    $("wardName").value = w.name;
    $("totalBeds").value = w.total;
    $("availableBeds").value = w.free;
    $("wardStatus").value = w.status;
    $("adminMessage").textContent = "Editing " + w.name;
    showPage("admin");
  }

  function saveWard() {
    const editId = $("wardEditId").value;
    const name = sanitizeText($("wardName").value);
    const totalText = $("totalBeds").value;
    const freeText = $("availableBeds").value;
    const total = Number(totalText);
    const free = Number(freeText);
    const status = $("wardStatus").value;

    if (!name || totalText === "" || freeText === "" || !Number.isInteger(total) || !Number.isInteger(free) || total <= 0 || free < 0 || free > total) {
      $("adminMessage").textContent = "Enter a ward name and valid whole-number bed counts (Available ≤ Total).";
      return;
    }

    if (editId) {
      const idx = wards.findIndex(w => w.id === editId);
      if (idx !== -1) {
        wards[idx] = { id: editId, name, total, free, status };
        addAudit("UPDATED_WARD", name);
        $("adminMessage").textContent = "Ward updated successfully.";
      }
    } else {
      wards.push({ id: "ward-" + Date.now(), name, total, free, status });
      addAudit("CREATED_WARD", name);
      $("adminMessage").textContent = "New ward provisioned successfully.";
    }

    clearWardForm(true);
    renderAll();
  }

  function removeWard(id) {
    const w = wards.find(x => x.id === id);
    if (!w) return;
    wards = wards.filter(x => x.id !== id);
    addAudit("REMOVED_WARD", w.name);
    renderAll();
  }

  function updateSession() {
    const mail = sanitizeText($("email").value) || "ops.admin@flowmed-nexus.demo";
    $("userStatus").textContent = mail;
    $("adminEmail").textContent = mail;
    $("authMessage").textContent = "Operator switched to " + mail;
  }

  function resetDemo() {
    wards = structuredClone(defaultWards);
    addAudit("RESET_TELEMETRY", "All Wards");
    renderAll();
    $("authMessage").textContent = "Default hospital ward telemetry restored.";
    $("aiLiveBanner").textContent = "✧ AI Copilot Insight: ICU capacity is at 80%. Recommend reserving 4 step-down beds in General Ward for incoming post-op transfers.";
  }

  document.querySelectorAll(".nav button[data-page]").forEach(b => b.addEventListener("click", () => showPage(b.dataset.page)));
  document.querySelectorAll("[data-nav-target]").forEach(b => b.addEventListener("click", () => showPage(b.dataset.navTarget)));
  $("heroSurgeBtn").addEventListener("click", simulateSurge);
  $("bedSurgeBtn").addEventListener("click", simulateSurge);
  $("bedResetBtn").addEventListener("click", resetDemo);
  $("accountResetBtn").addEventListener("click", resetDemo);
  $("patientSearch").addEventListener("input", () => filterTable("patientSearch", "patientRows"));
  $("appointmentSearch").addEventListener("input", () => filterTable("appointmentSearch", "appointmentRows"));
  document.querySelectorAll(".chip[data-prompt]").forEach(c => c.addEventListener("click", () => {
    $("question").value = c.dataset.prompt;
    askAI();
  }));
  $("askAiBtn").addEventListener("click", askAI);
  $("updateSessionBtn").addEventListener("click", updateSession);
  $("saveWardBtn").addEventListener("click", saveWard);
  $("clearWardBtn").addEventListener("click", () => clearWardForm(false));

  $("date").textContent = new Date().toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  renderAll();
})();
