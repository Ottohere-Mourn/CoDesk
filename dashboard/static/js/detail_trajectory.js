import { esc, fetchJson, fmtSec, fmtTokens, renderMarkdown } from "./utils.js";

function renderStepCard(step, expandAll) {
  const kindBadgeMap = {
    agent_message: "badge-green",
    reasoning: "badge-purple",
    cli: "badge-blue",
    gui_obs: "badge-cyan",
    gui_act: "badge-amber",
    other: "badge-red",
  };
  const bCls = kindBadgeMap[step.kind] || "badge-slate";
  const timeChip =
    step.rel_s != null
      ? `<span class="badge badge-slate" style="font-family:var(--mono)">T+${step.rel_s.toFixed(1)}s${step.duration_s ? ` · ${step.duration_s}s` : ""}</span>`
      : "";
  const winLine =
    step.win_before || step.win_after
      ? `<div class="event-win">桌面窗口：${esc(step.win_before || "—")} ${step.win_before !== step.win_after ? `→ <strong>${esc(step.win_after || "—")}</strong>` : ""}</div>`
      : "";

  let bodyHtml = "";
  if (step.kind === "agent_message") {
    bodyHtml = `<div class="md-view" style="max-height:none">${renderMarkdown(step.text || "")}</div>`;
  } else if (step.kind === "reasoning") {
    bodyHtml = `<pre class="code-pre light">${esc(step.text || "")}</pre>`;
  } else {
    const args = step.arguments;
    if (args && typeof args === "object" && typeof args.command === "string") {
      bodyHtml += `<pre class="code-pre" style="max-height:260px">$ ${esc(args.command)}</pre>`;
    } else if (args !== undefined && args !== null) {
      bodyHtml += `<pre class="code-pre light" style="max-height:200px">${esc(JSON.stringify(args, null, 2))}</pre>`;
    }
    if (step.base64_omitted && step.base64_omitted.length) {
      bodyHtml += `<div class="b64-pill">🖼️ 原始 Base64 截图已脱敏轻量化省略（${esc(step.base64_omitted.join(" · "))}），完整保留文本与无障碍树输出</div>`;
    }
    if (step.error) {
      bodyHtml += `<div class="err-box">${esc(typeof step.error === "string" ? step.error : JSON.stringify(step.error, null, 2))}</div>`;
    }
    if (step.result_text) {
      const txt = step.result_text;
      if (txt.length > 480) {
        const preview = txt.slice(0, 320);
        bodyHtml += `
          <details class="fold-box" ${expandAll ? "open" : ""}>
            <summary>返回结果 / 无障碍树 / 命令输出（共 ${txt.length} 字符，点击展开全文）</summary>
            <pre class="code-pre light" style="max-height:420px">${esc(txt)}</pre>
          </details>
          ${expandAll ? "" : `<pre class="code-pre light" style="max-height:110px;opacity:0.85;margin-top:4px">${esc(preview)}…</pre>`}`;
      } else {
        bodyHtml += `<pre class="code-pre light" style="margin-top:6px;max-height:240px">${esc(txt)}</pre>`;
      }
    }
    if (step.text && !step.result_text) {
      bodyHtml += `<pre class="code-pre light">${esc(step.text)}</pre>`;
    }
  }

  return `
    <article class="step-card kind-${esc(step.kind)}">
      <div class="step-head">
        <div class="badge-row">
          <span class="step-no">STEP #${step.step_no}</span>
          <span class="badge ${bCls}">${esc(step.kind_zh)}</span>
          ${timeChip}
          <strong>${esc(step.title)}</strong>
        </div>
        <span class="badge ${step.status === "failed" ? "badge-red" : "badge-slate"}">${esc(step.status || "completed")}</span>
      </div>
      ${winLine}
      ${bodyHtml}
    </article>`;
}

export async function renderTrajectoryTab(caseId, activeEp, mountEl) {
  let activeRole = activeEp.actors[0]?.role || "";
  let kindFilter = "";
  let kw = "";
  let expandAll = false;
  let currentTraj = null;

  async function loadRole(role) {
    activeRole = role;
    mountEl.innerHTML = `<div class="loading-banner">正在加载角色 <code>${esc(role)}</code> 的完整 Codex 执行轨迹…</div>`;
    currentTraj = await fetchJson(
      `/api/cases/${encodeURIComponent(caseId)}/episodes/${encodeURIComponent(activeEp.ep_name)}/trajectory/${encodeURIComponent(role)}`
    );
    draw();
  }

  function drawSteps() {
    if (!currentTraj) return;
    const q = kw.trim().toLowerCase();
    const steps = currentTraj.steps.filter((s) => {
      if (kindFilter && s.kind !== kindFilter) return false;
      if (q) {
        const hay = `${s.title} ${s.text || ""} ${s.result_text || ""} ${JSON.stringify(s.arguments || "")}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    const infoEl = mountEl.querySelector("#trajCount");
    if (infoEl) infoEl.textContent = `显示 ${steps.length} / ${currentTraj.total_steps} 个轨迹步骤`;
    const listEl = mountEl.querySelector("#trajStepList");
    listEl.innerHTML = steps.length
      ? steps.map((s) => renderStepCard(s, expandAll)).join("")
      : `<div class="loading-banner">未找到匹配的轨迹步骤。</div>`;
  }

  function draw() {
    const t = currentTraj;
    const u = t.usage || {};
    const c = t.counts || {};
    const roleSwitch = activeEp.actors
      .map(
        (a) =>
          `<button class="seg-btn ${a.role === activeRole ? "active" : ""}" data-role="${esc(a.role)}">${esc(a.name_zh)} (${esc(a.role)})</button>`
      )
      .join("");

    mountEl.innerHTML = `
      <div class="ctx-toolbar">
        <div>
          <h3 style="margin:0">单角色完整 Codex 轨迹回放（${esc(t.name_zh)}）</h3>
          <div class="muted-label">${esc(t.brief_zh)}</div>
        </div>
        <div class="segmented" id="trajRoleSwitch">${roleSwitch}</div>
      </div>

      <div class="tele-grid">
        <div class="tele-stat"><div class="lbl">总轨迹步骤</div><div class="val">${t.total_steps}</div></div>
        <div class="tele-stat"><div class="lbl">CLI / GUI 观 / GUI 动</div><div class="val">${c.cli || 0} / ${c.gui_obs || 0} / ${c.gui_act || 0}</div></div>
        <div class="tele-stat"><div class="lbl">智能体消息</div><div class="val">${c.agent_message || 0}</div></div>
        <div class="tele-stat"><div class="lbl">单角色耗时</div><div class="val">${fmtSec(t.actor_meta.wall_seconds)}</div></div>
        <div class="tele-stat"><div class="lbl">输入 / 缓存 Token</div><div class="val">${fmtTokens(u.input_tokens)} / ${fmtTokens(u.cached_input_tokens)}</div></div>
        <div class="tele-stat"><div class="lbl">输出 / 推理 Token</div><div class="val">${fmtTokens(u.output_tokens)} / ${fmtTokens(u.reasoning_output_tokens)}</div></div>
      </div>

      <div class="filter-bar">
        <input id="trajSearch" class="search-input" type="search" placeholder="在轨迹命令、工具参数、无障碍树输出与智能体汇报中全文检索…" value="${esc(kw)}" />
        <select id="trajKindSel" class="select-ctrl">
          <option value="">全部步骤类型 (${t.total_steps})</option>
          <option value="agent_message" ${kindFilter === "agent_message" ? "selected" : ""}>智能体汇报/消息 (${c.agent_message || 0})</option>
          <option value="gui_act" ${kindFilter === "gui_act" ? "selected" : ""}>GUI 交互动作 (${c.gui_act || 0})</option>
          <option value="gui_obs" ${kindFilter === "gui_obs" ? "selected" : ""}>GUI 桌面观察 (${c.gui_obs || 0})</option>
          <option value="cli" ${kindFilter === "cli" ? "selected" : ""}>CLI 终端命令 (${c.cli || 0})</option>
          <option value="other" ${kindFilter === "other" ? "selected" : ""}>错误与其他 (${c.other || 0})</option>
        </select>
        <button id="trajExpandBtn" class="btn-ghost">${expandAll ? "全部折叠长输出" : "全部展开长输出"}</button>
      </div>
      <div id="trajCount" class="filter-status"></div>
      <div id="trajStepList"></div>`;

    mountEl.querySelectorAll("#trajRoleSwitch .seg-btn").forEach((b) => {
      b.addEventListener("click", () => {
        if (b.dataset.role !== activeRole) loadRole(b.dataset.role);
      });
    });
    mountEl.querySelector("#trajSearch").addEventListener("input", (e) => { kw = e.target.value; drawSteps(); });
    mountEl.querySelector("#trajKindSel").addEventListener("change", (e) => { kindFilter = e.target.value; drawSteps(); });
    mountEl.querySelector("#trajExpandBtn").addEventListener("click", () => {
      expandAll = !expandAll;
      mountEl.querySelector("#trajExpandBtn").textContent = expandAll ? "全部折叠长输出" : "全部展开长输出";
      drawSteps();
    });

    drawSteps();
  }

  await loadRole(activeRole);
}
