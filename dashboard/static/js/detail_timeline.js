import { esc, fmtSec } from "./utils.js";

const CHAN_COLORS = {
  cli: "#2563eb",
  gui_obs: "#0891b2",
  gui_act: "#d97706",
  other: "#64748b",
};

const CHAN_ZH = {
  cli: "CLI 命令",
  gui_obs: "GUI 观察",
  gui_act: "GUI 动作",
  other: "其他",
};

function buildSwimlaneSvg(tl) {
  const w = 1040;
  const h = 136;
  const leftPad = 170;
  const rightPad = 24;
  const plotW = w - leftPad - rightPad;
  const span = Math.max(tl.duration_span_s || 1, 1);
  const r0 = tl.roles[0] || { role: "A", name_zh: "角色 A" };
  const r1 = tl.roles[1] || { role: "B", name_zh: "角色 B" };

  const ticks = [0, 0.25, 0.5, 0.75, 1]
    .map((p) => {
      const x = leftPad + plotW * p;
      return `<line x1="${x}" y1="16" x2="${x}" y2="112" stroke="#e2e8f0" stroke-dasharray="3,3" />
              <text x="${x}" y="128" text-anchor="middle" fill="#64748b" font-size="11" font-family="monospace">${fmtSec(span * p)}</text>`;
    })
    .join("");

  const bars = tl.events
    .map((ev) => {
      const x = leftPad + (ev.rel_s / span) * plotW;
      const bw = Math.max(3, Math.min(28, ((ev.duration_s || 0.8) / span) * plotW));
      const y = ev.role === r0.role ? 30 : 74;
      const color = CHAN_COLORS[ev.channel] || "#64748b";
      const ring = ev.is_focus_flip
        ? `<circle cx="${x + bw / 2}" cy="${y - 6}" r="3" fill="#dc2626" />`
        : ev.clipboard_changed
        ? `<circle cx="${x + bw / 2}" cy="${y - 6}" r="3" fill="#7c3aed" />`
        : "";
      const tip = `#${ev.idx} [${ev.role_zh}] T+${ev.rel_s}s · ${ev.tool_zh}`;
      return `<g class="swim-hit" data-ev-idx="${ev.idx}" style="cursor:pointer">
        <title>${esc(tip)}</title>
        <rect x="${x.toFixed(1)}" y="${y}" width="${bw.toFixed(1)}" height="24" rx="3" fill="${color}" opacity="0.88" />
        ${ring}
      </g>`;
    })
    .join("");

  return `
    <svg viewBox="0 0 ${w} ${h}" width="100%" style="min-width:740px;display:block">
      <rect x="${leftPad}" y="26" width="${plotW}" height="32" rx="6" fill="#eff6ff" />
      <rect x="${leftPad}" y="70" width="${plotW}" height="32" rx="6" fill="#f5f3ff" />
      ${ticks}
      <text x="12" y="46" fill="#1e40af" font-size="12.5" font-weight="700">${esc(r0.name_zh)}</text>
      <text x="12" y="90" fill="#6d28d9" font-size="12.5" font-weight="700">${esc(r1.name_zh)}</text>
      ${bars}
    </svg>`;
}

export function renderTimelineTab(tl, mountEl) {
  let roleFilter = "";
  let chanFilter = "";
  let onlyConflict = false;
  let kw = "";
  const r0 = tl.roles[0]?.role || "";

  const tel = tl.telemetry || {};
  const cs = tl.computed_stats || {};
  const race = tl.race_awareness || {};

  const statsCards = [
    { lbl: "总交互事件", val: tl.total_events },
    { lbl: "时间跨度", val: fmtSec(tl.duration_span_s) },
    { lbl: "角色交错切换", val: tel.interleaving_role_switches ?? cs.role_switches },
    { lbl: "焦点翻转次数", val: tel.focus_flips ?? cs.focus_flips },
    { lbl: "误路由按键", val: tel.misrouted_keystrokes ?? "—" },
    { lbl: "剪贴板变更", val: tel.clipboard_changes ?? cs.clipboard_changes },
    { lbl: "并发重叠时长", val: tel.overlap_seconds != null ? fmtSec(tel.overlap_seconds) : "—" },
    { lbl: "自发竞争感知", val: race.autonomous_race_aware ? "是" : "否" },
  ];

  function renderEvents() {
    const q = kw.trim().toLowerCase();
    const list = tl.events.filter((ev) => {
      if (roleFilter && ev.role !== roleFilter) return false;
      if (chanFilter && ev.channel !== chanFilter) return false;
      if (onlyConflict && !ev.is_role_switch && !ev.is_focus_flip && !ev.clipboard_changed) return false;
      if (q) {
        const hay = `${ev.role} ${ev.role_zh} ${ev.tool} ${ev.tool_zh} ${ev.win_before} ${ev.win_after} ${ev.args_preview}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    const countEl = mountEl.querySelector("#tlCount");
    if (countEl) countEl.textContent = `显示 ${list.length} / ${tl.total_events} 条时间线事件（数据源：${tl.source}）`;

    const listEl = mountEl.querySelector("#tlEventList");
    listEl.innerHTML = list.length
      ? list
          .map((ev) => {
            const isB = ev.role !== r0;
            const badges = [
              `<span class="badge ${isB ? "badge-purple" : "badge-blue"}">${esc(ev.role_zh)}</span>`,
              `<span class="badge badge-slate">${esc(CHAN_ZH[ev.channel] || ev.channel)}</span>`,
            ];
            if (ev.is_role_switch) badges.push(`<span class="badge badge-amber">角色切换点</span>`);
            if (ev.is_focus_flip) badges.push(`<span class="badge badge-red">窗口焦点变化</span>`);
            if (ev.clipboard_changed) badges.push(`<span class="badge badge-purple">剪贴板变更</span>`);
            const winLine =
              ev.win_before || ev.win_after
                ? `<div class="event-win">窗口：${esc(ev.win_before || "—")} ${ev.win_before !== ev.win_after ? `→ <strong>${esc(ev.win_after || "—")}</strong>` : ""}</div>`
                : "";
            return `
              <div class="event-row ${isB ? "role-b" : ""}" id="tl-ev-${ev.idx}">
                <div class="event-head">
                  <div class="badge-row">
                    <span class="step-no">#${ev.idx}</span>
                    <span class="badge badge-slate" style="font-family:var(--mono)">T+${ev.rel_s.toFixed(1)}s${ev.duration_s ? ` (${ev.duration_s}s)` : ""}</span>
                    ${badges.join("")}
                    <strong>${esc(ev.tool_zh)}</strong>
                    <code style="font-size:11.5px;color:var(--muted)">${esc(ev.tool)}</code>
                  </div>
                </div>
                ${winLine}
                ${ev.args_preview ? `<div class="event-preview">${esc(ev.args_preview)}</div>` : ""}
                <details class="fold-box">
                  <summary>查看完整参数 JSON</summary>
                  <pre class="code-pre light">${esc(JSON.stringify(ev.args, null, 2))}</pre>
                </details>
              </div>`;
          })
          .join("")
      : `<div class="loading-banner">当前筛选条件下无匹配时间线事件。</div>`;
  }

  const raceDetails =
    race && race.roles
      ? `<details class="fold-box" style="margin-bottom:14px">
          <summary>查看自发竞争感知信号与命令证据样本（race_awareness）</summary>
          <pre class="code-pre light">${esc(JSON.stringify(race, null, 2))}</pre>
        </details>`
      : "";

  mountEl.innerHTML = `
    <div class="tele-grid">
      ${statsCards.map((s) => `<div class="tele-stat"><div class="lbl">${esc(s.lbl)}</div><div class="val">${esc(s.val)}</div></div>`).join("")}
    </div>
    ${raceDetails}
    <div class="swimlane-wrap">
      <div class="swim-legend">
        <strong>双角色并发泳道图（点击色块跳转事件）：</strong>
        <span><i class="dot" style="background:#2563eb"></i>CLI 命令</span>
        <span><i class="dot" style="background:#0891b2"></i>GUI 观察</span>
        <span><i class="dot" style="background:#d97706"></i>GUI 动作</span>
        <span><i class="dot" style="background:#dc2626;border-radius:50%"></i>红点 = 窗口焦点变化</span>
        <span><i class="dot" style="background:#7c3aed;border-radius:50%"></i>紫点 = 剪贴板变更</span>
      </div>
      ${buildSwimlaneSvg(tl)}
    </div>
    <div class="filter-bar">
      <input id="tlSearch" class="search-input" type="search" placeholder="过滤工具名、窗口标题或命令参数…" />
      <select id="tlRoleSel" class="select-ctrl">
        <option value="">全部角色</option>
        ${tl.roles.map((r) => `<option value="${esc(r.role)}">${esc(r.name_zh)} (${esc(r.role)})</option>`).join("")}
      </select>
      <select id="tlChanSel" class="select-ctrl">
        <option value="">全部通道</option>
        <option value="gui_act">仅 GUI 动作</option>
        <option value="gui_obs">仅 GUI 观察</option>
        <option value="cli">仅 CLI 命令</option>
      </select>
      <label class="check-pill">
        <input type="checkbox" id="tlOnlyConflict" />
        <span>仅看切换/焦点/剪贴板冲突点</span>
      </label>
    </div>
    <div id="tlCount" class="filter-status"></div>
    <div id="tlEventList" class="event-list"></div>`;

  mountEl.querySelector("#tlSearch").addEventListener("input", (e) => { kw = e.target.value; renderEvents(); });
  mountEl.querySelector("#tlRoleSel").addEventListener("change", (e) => { roleFilter = e.target.value; renderEvents(); });
  mountEl.querySelector("#tlChanSel").addEventListener("change", (e) => { chanFilter = e.target.value; renderEvents(); });
  mountEl.querySelector("#tlOnlyConflict").addEventListener("change", (e) => { onlyConflict = e.target.checked; renderEvents(); });

  mountEl.querySelectorAll(".swim-hit").forEach((g) => {
    g.addEventListener("click", () => {
      const target = mountEl.querySelector(`#tl-ev-${g.dataset.evIdx}`);
      if (target) {
        mountEl.querySelectorAll(".event-row.highlight").forEach((n) => n.classList.remove("highlight"));
        target.classList.add("highlight");
        target.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  });

  renderEvents();
}
