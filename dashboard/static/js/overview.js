import { esc, fmtDelta, fmtPct, fmtScore, scoreClass } from "./utils.js";

export function renderKpiGrid(ov) {
  const sol = ov.overall_summary["gpt-6.1-sol"];
  const ast = ov.overall_summary["gpt-6-astra"];
  const ns = ov.nonsat_summary;
  const cards = [
    {
      label: "归档规模（4 套件精选）",
      value: `${ov.total_cases} 题 / ${ov.total_episodes} 局`,
      sub: `<span>${ov.total_agent_trajectories} 条 Non-YOLO 角色轨迹</span><span>推理档位：<code>${esc(ov.reasoning_effort)}</code></span>`,
    },
    {
      label: "GPT-6.1-Sol (high) 全量 23 题",
      value: `${fmtPct(sol.baseline_mean)} → ${fmtPct(sol.shared_mean)}`,
      sub: `<span>共享退化 ${fmtDelta(sol.delta_mean)}</span><span>联合通过 ${esc(sol.baseline_joint_pass)} → ${esc(sol.shared_joint_pass)}</span>`,
    },
    {
      label: "GPT-6-Astra (high) 全量 23 题",
      value: `${fmtPct(ast.baseline_mean)} → ${fmtPct(ast.shared_mean)}`,
      sub: `<span>共享退化 ${fmtDelta(ast.delta_mean)}</span><span>联合通过 ${esc(ast.baseline_joint_pass)} → ${esc(ast.shared_joint_pass)}</span>`,
    },
    {
      label: `非饱和区分核心子集（${ns.count} 题）`,
      value: `Sol ${fmtPct(ns.sol_shared_mean)} · Astra ${fmtPct(ns.astra_shared_mean)}`,
      sub: `<span>Sol ${fmtPct(ns.sol_baseline_mean)}→${fmtPct(ns.sol_shared_mean)} (${fmtDelta(ns.sol_shared_mean - ns.sol_baseline_mean)})</span><span>Astra ${fmtPct(ns.astra_baseline_mean)}→${fmtPct(ns.astra_shared_mean)} (${fmtDelta(ns.astra_shared_mean - ns.astra_baseline_mean)})</span>`,
    },
  ];
  document.getElementById("kpiGrid").innerHTML = cards
    .map(
      (c) => `
      <div class="kpi-card">
        <div class="kpi-label">${c.label}</div>
        <div class="kpi-value">${c.value}</div>
        <div class="kpi-sub">${c.sub}</div>
      </div>`
    )
    .join("");
}

export function renderAggCharts(ov, dim, activeFilters, onPick) {
  const rows = ov.taxonomy[dim] || [];
  const wrap = document.getElementById("aggChartGrid");
  wrap.innerHTML = rows
    .map((r) => {
      const isSelected =
        (dim === "batches" && activeFilters.batch === r.key) ||
        (dim === "mechanisms" && activeFilters.mech === r.key) ||
        (dim === "domains" && activeFilters.domain === r.key);
      return `
        <div class="agg-card ${isSelected ? "active-filter" : ""}" style="border-top-color:${esc(r.color)}" data-dim="${esc(dim)}" data-key="${esc(r.key)}">
          <div class="agg-head">
            <div class="agg-name">${esc(r.label)}</div>
            <span class="agg-count">${r.count} 题</span>
          </div>
          ${r.desc ? `<div class="agg-desc">${esc(r.desc)}</div>` : ""}
          <div class="mini-bar-row">
            <span style="color:#2563eb;font-weight:700">Sol</span>
            <div class="mini-bar-track">
              <div class="mini-bar-base" style="width:${(r.sol_baseline * 100).toFixed(1)}%;background:#2563eb"></div>
              <div class="mini-bar-shared" style="width:${(r.sol_shared * 100).toFixed(1)}%;background:#2563eb"></div>
            </div>
            <span class="mini-bar-num">${fmtPct(r.sol_shared)} ${fmtDelta(r.sol_delta)}</span>
          </div>
          <div class="mini-bar-row">
            <span style="color:#7c3aed;font-weight:700">Astra</span>
            <div class="mini-bar-track">
              <div class="mini-bar-base" style="width:${(r.astra_baseline * 100).toFixed(1)}%;background:#7c3aed"></div>
              <div class="mini-bar-shared" style="width:${(r.astra_shared * 100).toFixed(1)}%;background:#7c3aed"></div>
            </div>
            <span class="mini-bar-num">${fmtPct(r.astra_shared)} ${fmtDelta(r.astra_delta)}</span>
          </div>
        </div>`;
    })
    .join("");

  wrap.querySelectorAll(".agg-card").forEach((el) => {
    el.addEventListener("click", () => onPick(el.dataset.dim, el.dataset.key));
  });
}

function renderCaseCard(c) {
  const swBadges = c.software_stack
    .map((s) => `<span class="badge badge-slate">${esc(s)}</span>`)
    .join("");
  const sensBadge =
    c.sensitivity_cat === "strong_drop"
      ? `<span class="badge badge-red">${esc(c.sensitivity_zh)}</span>`
      : c.sensitivity_cat === "saturated"
      ? `<span class="badge badge-green">${esc(c.sensitivity_zh)}</span>`
      : `<span class="badge badge-amber">${esc(c.sensitivity_zh)}</span>`;
  const rolesHtml = (c.roles || [])
    .map(
      (r) => `
      <div class="role-chip">
        <strong>${esc(r.name_zh)}</strong>
        <code>${esc(r.role)}</code>
      </div>`
    )
    .join("");

  return `
    <article class="case-card" data-case-id="${esc(c.id)}">
      <div class="case-card-top">
        <div class="badge-row">
          <span class="case-id">${esc(c.id)}</span>
          <span class="badge badge-blue">${esc(c.batch_short)}</span>
          <span class="badge badge-purple">${esc(c.mechanism_short)}</span>
        </div>
        ${sensBadge}
      </div>
      <div class="case-title-zh" data-open-tab="summary">${esc(c.title_zh)}</div>
      <div class="case-summary">${esc(c.summary_zh)}</div>
      <div class="case-contention"><strong>核心竞争原语：</strong>${esc(c.contention_zh)}</div>
      <div class="badge-row">${swBadges}</div>
      <div class="case-roles">${rolesHtml}</div>
      <div class="score-pair">
        <div class="score-box">
          <div class="score-box-head"><span style="color:#2563eb">GPT-6.1-Sol</span>${fmtDelta(c.sol.delta)}</div>
          <div class="score-vals">${fmtScore(c.sol.baseline.mean_score)} → ${fmtScore(c.sol.shared.mean_score)}</div>
        </div>
        <div class="score-box">
          <div class="score-box-head"><span style="color:#7c3aed">GPT-6-Astra</span>${fmtDelta(c.astra.delta)}</div>
          <div class="score-vals">${fmtScore(c.astra.baseline.mean_score)} → ${fmtScore(c.astra.shared.mean_score)}</div>
        </div>
      </div>
      <div class="card-actions">
        <button class="btn-ghost" data-open-tab="context">任务上下文</button>
        <button class="btn-ghost" data-open-tab="timeline">共享时间线</button>
        <button class="btn-primary" data-open-tab="trajectory">完整轨迹</button>
      </div>
    </article>`;
}

function renderCompactTable(cases) {
  return `
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th>题号</th><th>批次</th><th>竞争机制</th><th>中文任务名称</th>
            <th>Sol 基线→共享</th><th>Astra 基线→共享</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          ${cases
            .map(
              (c) => `
            <tr data-case-id="${esc(c.id)}">
              <td><span class="case-id">${esc(c.id)}</span></td>
              <td><span class="badge badge-blue">${esc(c.batch_short)}</span></td>
              <td><span class="badge badge-purple">${esc(c.mechanism_short)}</span></td>
              <td><strong>${esc(c.title_zh)}</strong><div class="muted-label">${esc(c.software_stack.join(" · "))}</div></td>
              <td style="font-family:var(--mono)">${fmtScore(c.sol.baseline.mean_score)} → ${fmtScore(c.sol.shared.mean_score)} ${fmtDelta(c.sol.delta)}</td>
              <td style="font-family:var(--mono)">${fmtScore(c.astra.baseline.mean_score)} → ${fmtScore(c.astra.shared.mean_score)} ${fmtDelta(c.astra.delta)}</td>
              <td><button class="btn-primary" data-open-tab="trajectory">查看轨迹</button></td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    </div>`;
}

export function renderCaseExplorer(ov, cases, groupBy, onOpenCase) {
  const container = document.getElementById("caseContainer");
  document.getElementById("filterStatus").textContent = `当前筛选命中 ${cases.length} / ${ov.total_cases} 道基准（共 ${cases.length * 4} 局 / ${cases.length * 8} 条角色轨迹）`;

  if (!cases.length) {
    container.innerHTML = `<div class="loading-banner">未找到匹配的 Case，请尝试放宽筛选条件。</div>`;
    return;
  }
  if (groupBy === "flat") {
    container.innerHTML = renderCompactTable(cases);
  } else {
    const metaLookup = {};
    const taxMap = {
      mechanism: ov.taxonomy.mechanisms,
      batch: ov.taxonomy.batches,
      domain_cat: ov.taxonomy.domains,
      sensitivity_cat: ov.taxonomy.sensitivity,
    }[groupBy] || [];
    taxMap.forEach((m) => (metaLookup[m.key] = m));

    const grouped = new Map();
    for (const m of taxMap) grouped.set(m.key, []);
    for (const c of cases) {
      const k = c[groupBy];
      if (!grouped.has(k)) grouped.set(k, []);
      grouped.get(k).push(c);
    }

    let html = "";
    for (const [k, items] of grouped.entries()) {
      if (!items.length) continue;
      const m = metaLookup[k] || { label: k, color: "#2563eb", desc: "" };
      html += `
        <div class="group-section">
          <div class="group-header" style="border-left-color:${esc(m.color)}">
            <div>
              <div class="group-title">${esc(m.label)}（${items.length} 题）</div>
              ${m.desc ? `<div class="group-sub">${esc(m.desc)}</div>` : ""}
            </div>
          </div>
          <div class="case-grid">${items.map(renderCaseCard).join("")}</div>
        </div>`;
    }
    container.innerHTML = html;
  }

  container.querySelectorAll("[data-open-tab]").forEach((el) => {
    el.addEventListener("click", () => {
      const card = el.closest("[data-case-id]");
      if (card) onOpenCase(card.dataset.caseId, null, el.dataset.openTab);
    });
  });
}

export function renderMatrixView(ov, onOpenCase) {
  const rowsHtml = ov.cases
    .map((c) => {
      const baseEpSol = c.episode_dirs.find((e) => !e.startsWith("shared_") && e.includes("sol")) || "";
      const shEpSol = c.episode_dirs.find((e) => e.startsWith("shared_") && e.includes("sol")) || "";
      const baseEpAst = c.episode_dirs.find((e) => !e.startsWith("shared_") && e.includes("astra")) || "";
      const shEpAst = c.episode_dirs.find((e) => e.startsWith("shared_") && e.includes("astra")) || "";
      const astTel = (c.shared_metrics && c.shared_metrics["gpt-6-astra"]) || {};
      const sw = astTel.interleaving_role_switches ?? "—";
      const flips = astTel.focus_flips ?? "—";
      return `
        <tr>
          <td><span class="case-id" style="cursor:pointer" data-cid="${esc(c.id)}" data-ep="${esc(shEpAst)}">${esc(c.id)}</span></td>
          <td><span class="badge badge-blue">${esc(c.batch_short)}</span></td>
          <td><span class="badge badge-purple">${esc(c.mechanism_short)}</span></td>
          <td style="min-width:240px"><strong>${esc(c.title_zh)}</strong></td>
          <td class="score-cell ${scoreClass(c.sol.baseline.mean_score)}" data-cid="${esc(c.id)}" data-ep="${esc(baseEpSol)}">${fmtScore(c.sol.baseline.mean_score)}</td>
          <td class="score-cell ${scoreClass(c.sol.shared.mean_score)}" data-cid="${esc(c.id)}" data-ep="${esc(shEpSol)}">${fmtScore(c.sol.shared.mean_score)}</td>
          <td style="text-align:center;font-family:var(--mono)">${fmtDelta(c.sol.delta)}</td>
          <td class="score-cell ${scoreClass(c.astra.baseline.mean_score)}" data-cid="${esc(c.id)}" data-ep="${esc(baseEpAst)}">${fmtScore(c.astra.baseline.mean_score)}</td>
          <td class="score-cell ${scoreClass(c.astra.shared.mean_score)}" data-cid="${esc(c.id)}" data-ep="${esc(shEpAst)}">${fmtScore(c.astra.shared.mean_score)}</td>
          <td style="text-align:center;font-family:var(--mono)">${fmtDelta(c.astra.delta)}</td>
          <td style="font-family:var(--mono);white-space:nowrap">切换 ${sw} / 焦点 ${flips}</td>
        </tr>`;
    })
    .join("");

  const wrap = document.getElementById("matrixWrap");
  wrap.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>题号</th><th>批次</th><th>竞争机制</th><th>中文任务名</th>
          <th>Sol 基线</th><th>Sol 共享</th><th>Sol Δ</th>
          <th>Astra 基线</th><th>Astra 共享</th><th>Astra Δ</th>
          <th>Astra 共享交错/焦点</th>
        </tr>
      </thead>
      <tbody>${rowsHtml}</tbody>
    </table>`;

  wrap.querySelectorAll("[data-cid]").forEach((el) => {
    el.addEventListener("click", () => onOpenCase(el.dataset.cid, el.dataset.ep, "trajectory"));
  });
}
