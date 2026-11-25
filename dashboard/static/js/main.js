import { esc, fetchJson } from "./utils.js";
import { renderAggCharts, renderCaseExplorer, renderKpiGrid, renderMatrixView } from "./overview.js";
import { renderCaseHeader, renderEpisodeStrip, renderSummaryTab } from "./detail_summary.js";
import { renderContextTab } from "./detail_context.js";
import { renderTimelineTab } from "./detail_timeline.js";
import { renderTrajectoryTab } from "./detail_trajectory.js";

const state = {
  overview: null,
  view: "overview",
  aggDim: "mechanisms",
  groupBy: "mechanism",
  filters: { q: "", batch: "", mech: "", domain: "", sw: "", onlyDrop: false, sort: "default" },
  detail: null,
  activeCaseId: null,
  activeEpName: null,
  activeTab: "summary",
};

function setView(viewName) {
  state.view = viewName;
  document.querySelectorAll(".view-section").forEach((s) => s.classList.add("hidden"));
  document.getElementById(`view-${viewName}`)?.classList.remove("hidden");
  document.querySelectorAll(".nav-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === viewName);
  });
  window.scrollTo({ top: 0, behavior: "instant" });
}

function getFilteredCases() {
  const f = state.filters;
  const q = f.q.trim().toLowerCase();
  let items = state.overview.cases.filter((c) => {
    if (f.batch && c.batch !== f.batch) return false;
    if (f.mech && c.mechanism !== f.mech) return false;
    if (f.domain && c.domain_cat !== f.domain) return false;
    if (f.sw && !c.software_stack.includes(f.sw)) return false;
    if (f.onlyDrop && c.sensitivity_cat !== "strong_drop") return false;
    if (q) {
      const rolesStr = (c.roles || []).map((r) => `${r.role} ${r.name_zh}`).join(" ");
      const hay = `${c.id} ${c.title_zh} ${c.title_en} ${c.summary_zh} ${c.contention_zh} ${c.software_stack.join(" ")} ${rolesStr}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  if (f.sort === "worst_drop") items = [...items].sort((a, b) => a.worst_drop - b.worst_drop);
  else if (f.sort === "astra_shared") items = [...items].sort((a, b) => a.astra.shared.mean_score - b.astra.shared.mean_score);
  else if (f.sort === "sol_shared") items = [...items].sort((a, b) => a.sol.shared.mean_score - b.sol.shared.mean_score);
  else if (f.sort === "model_gap") items = [...items].sort((a, b) => Math.abs(b.model_gap_shared) - Math.abs(a.model_gap_shared));
  return items;
}

function refreshOverview() {
  renderAggCharts(state.overview, state.aggDim, state.filters, (dim, key) => {
    if (dim === "batches") {
      state.filters.batch = state.filters.batch === key ? "" : key;
      document.getElementById("filterBatch").value = state.filters.batch;
    } else if (dim === "mechanisms") {
      state.filters.mech = state.filters.mech === key ? "" : key;
      document.getElementById("filterMech").value = state.filters.mech;
    } else if (dim === "domains") {
      state.filters.domain = state.filters.domain === key ? "" : key;
    }
    refreshOverview();
  });
  renderCaseExplorer(state.overview, getFilteredCases(), state.groupBy, openCase);
}

async function renderActiveDetailTab() {
  const mount = document.getElementById("detailTabContent");
  const ep = state.detail.episodes.find((e) => e.ep_name === state.activeEpName) || state.detail.episodes[0];
  if (!ep) return;
  state.activeEpName = ep.ep_name;

  document.querySelectorAll("#detailTabs .dtab").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === state.activeTab);
  });

  if (state.activeTab === "summary") {
    mount.innerHTML = renderSummaryTab(state.detail, ep);
    return;
  }
  mount.innerHTML = `<div class="loading-banner">正在加载数据…</div>`;
  try {
    if (state.activeTab === "context") {
      const ctx = await fetchJson(`/api/cases/${encodeURIComponent(state.activeCaseId)}/episodes/${encodeURIComponent(ep.ep_name)}/context`);
      renderContextTab(ctx, mount);
    } else if (state.activeTab === "timeline") {
      const tl = await fetchJson(`/api/cases/${encodeURIComponent(state.activeCaseId)}/episodes/${encodeURIComponent(ep.ep_name)}/timeline`);
      renderTimelineTab(tl, mount);
    } else if (state.activeTab === "trajectory") {
      await renderTrajectoryTab(state.activeCaseId, ep, mount);
    }
  } catch (err) {
    mount.innerHTML = `<div class="err-box">加载失败：${esc(err.message)}</div>`;
  }
}

async function openCase(caseId, epName = null, tab = "summary") {
  state.activeCaseId = caseId;
  state.activeTab = tab || "summary";
  const navBtn = document.getElementById("navDetailBtn");
  navBtn.disabled = false;
  navBtn.textContent = `单题工作台 · ${caseId}`;
  setView("detail");
  document.getElementById("caseQuickSelect").value = caseId;
  document.getElementById("detailTabContent").innerHTML = `<div class="loading-banner">正在加载 ${esc(caseId)} 评测详情…</div>`;

  const detail = await fetchJson(`/api/cases/${encodeURIComponent(caseId)}`);
  state.detail = detail;
  state.activeEpName = epName && detail.episodes.some((e) => e.ep_name === epName)
    ? epName
    : (detail.episodes.find((e) => e.mode === "shared" && e.model === "gpt-6-astra")?.ep_name || detail.episodes[0]?.ep_name);

  renderCaseHeader(detail);
  const onSelectEp = (pickedEp) => {
    state.activeEpName = pickedEp;
    renderEpisodeStrip(detail, state.activeEpName, onSelectEp);
    renderActiveDetailTab();
  };
  renderEpisodeStrip(detail, state.activeEpName, onSelectEp);
  await renderActiveDetailTab();
}

function bindEvents() {
  document.getElementById("brandHome").addEventListener("click", () => setView("overview"));
  document.getElementById("backOverviewBtn").addEventListener("click", () => setView("overview"));
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!btn.disabled) setView(btn.dataset.view);
    });
  });
  document.querySelectorAll("#aggDimSwitch .seg-btn").forEach((b) => {
    b.addEventListener("click", () => {
      state.aggDim = b.dataset.dim;
      document.querySelectorAll("#aggDimSwitch .seg-btn").forEach((x) => x.classList.toggle("active", x === b));
      refreshOverview();
    });
  });
  document.querySelectorAll("#groupBySwitch .seg-btn").forEach((b) => {
    b.addEventListener("click", () => {
      state.groupBy = b.dataset.group;
      document.querySelectorAll("#groupBySwitch .seg-btn").forEach((x) => x.classList.toggle("active", x === b));
      refreshOverview();
    });
  });
  document.getElementById("searchInput").addEventListener("input", (e) => { state.filters.q = e.target.value; refreshOverview(); });
  document.getElementById("filterBatch").addEventListener("change", (e) => { state.filters.batch = e.target.value; refreshOverview(); });
  document.getElementById("filterMech").addEventListener("change", (e) => { state.filters.mech = e.target.value; refreshOverview(); });
  document.getElementById("filterSoftware").addEventListener("change", (e) => { state.filters.sw = e.target.value; refreshOverview(); });
  document.getElementById("sortSelect").addEventListener("change", (e) => { state.filters.sort = e.target.value; refreshOverview(); });
  document.getElementById("onlyDropCheck").addEventListener("change", (e) => { state.filters.onlyDrop = e.target.checked; refreshOverview(); });
  document.getElementById("resetFiltersBtn").addEventListener("click", () => {
    state.filters = { q: "", batch: "", mech: "", domain: "", sw: "", onlyDrop: false, sort: "default" };
    document.getElementById("searchInput").value = "";
    document.getElementById("filterBatch").value = "";
    document.getElementById("filterMech").value = "";
    document.getElementById("filterSoftware").value = "";
    document.getElementById("sortSelect").value = "default";
    document.getElementById("onlyDropCheck").checked = false;
    refreshOverview();
  });
  document.getElementById("caseQuickSelect").addEventListener("change", (e) => openCase(e.target.value, null, state.activeTab));
  document.querySelectorAll("#detailTabs .dtab").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeTab = btn.dataset.tab;
      renderActiveDetailTab();
    });
  });
}

async function init() {
  try {
    const ov = await fetchJson("/api/overview");
    state.overview = ov;
    document.getElementById("loadingBanner").classList.add("hidden");

    const batchSel = document.getElementById("filterBatch");
    ov.taxonomy.batches.forEach((b) => batchSel.insertAdjacentHTML("beforeend", `<option value="${esc(b.key)}">${esc(b.label)} (${b.count})</option>`));
    const mechSel = document.getElementById("filterMech");
    ov.taxonomy.mechanisms.forEach((m) => mechSel.insertAdjacentHTML("beforeend", `<option value="${esc(m.key)}">${esc(m.label)} (${m.count})</option>`));
    const swSel = document.getElementById("filterSoftware");
    ov.taxonomy.software.forEach((s) => swSel.insertAdjacentHTML("beforeend", `<option value="${esc(s.name)}">${esc(s.name)} (${s.count})</option>`));
    const quickSel = document.getElementById("caseQuickSelect");
    ov.cases.forEach((c) => quickSel.insertAdjacentHTML("beforeend", `<option value="${esc(c.id)}">${esc(c.id)} · ${esc(c.title_zh)}</option>`));

    renderKpiGrid(ov);
    renderMatrixView(ov, openCase);
    bindEvents();
    refreshOverview();
    setView("overview");
  } catch (err) {
    document.getElementById("loadingBanner").innerHTML = `<div class="err-box">初始化失败：${esc(err.message)}</div>`;
  }
}

init();
