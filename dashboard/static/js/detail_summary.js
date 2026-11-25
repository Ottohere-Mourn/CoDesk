import { esc, fmtScore, fmtSec, fmtTokens } from "./utils.js";

export function renderCaseHeader(detail) {
  const c = detail.case;
  const sw = c.software_stack.map((s) => `<span class="badge badge-slate">${esc(s)}</span>`).join("");
  const rolesList = (c.roles || [])
    .map((r) => `<li><strong>${esc(r.name_zh)}</strong> (<code>${esc(r.role)}</code>)：${esc(r.brief_zh)}</li>`)
    .join("");
  document.getElementById("caseHeaderCard").innerHTML = `
    <div class="detail-hero-grid">
      <div>
        <div class="badge-row">
          <span class="case-id">${esc(c.id)}</span>
          <span class="badge badge-blue">${esc(c.batch_label)}</span>
          <span class="badge badge-purple">${esc(c.mechanism_label)}</span>
          <span class="badge badge-cyan">${esc(c.domain_label)}</span>
        </div>
        <h1 class="detail-title">${esc(c.title_zh)}</h1>
        <div class="detail-en">${esc(c.title_en)}</div>
        <p class="case-summary" style="margin:0 0 10px">${esc(c.summary_zh)}</p>
        <div class="case-contention"><strong>核心共享冲突原语：</strong>${esc(c.contention_zh)}</div>
      </div>
      <div>
        <dl class="meta-kv">
          <dt>软件栈</dt><dd><div class="badge-row">${sw}</div></dd>
          <dt>角色分工</dt><dd><ul style="margin:0;padding-left:16px">${rolesList}</ul></dd>
          <dt>任务源码</dt><dd><code>${esc(c.source_file)}</code></dd>
          <dt>评测执行器</dt><dd><code>${esc(c.runner_file)}</code></dd>
          <dt>轨迹目录</dt><dd><code>${esc(c.trajectory_dir)}</code></dd>
        </dl>
      </div>
    </div>`;
}

export function renderEpisodeStrip(detail, activeEpName, onSelectEp) {
  const wrap = document.getElementById("episodeStrip");
  wrap.innerHTML = detail.episodes
    .map((ep) => {
      const isAct = ep.ep_name === activeEpName;
      const passBadge = ep.joint_pass
        ? `<span class="badge badge-green">联合通过</span>`
        : `<span class="badge badge-red">未全通过</span>`;
      const modelColor = ep.model === "gpt-6-astra" ? "#7c3aed" : "#2563eb";
      return `
        <button class="ep-pill ${isAct ? "active" : ""}" data-ep="${esc(ep.ep_name)}">
          <div class="ep-pill-head">
            <span style="color:${modelColor}">${esc(ep.model_zh)}</span>
            ${passBadge}
          </div>
          <div style="font-size:12px;font-weight:600;color:var(--ink-2)">${esc(ep.mode_zh)}</div>
          <div class="ep-pill-sub">
            <span>均分 ${fmtScore(ep.mean_score)} (A:${fmtScore(ep.score_a)} / B:${fmtScore(ep.score_b)})</span>
            <span>${fmtSec(ep.wall_seconds)}</span>
          </div>
        </button>`;
    })
    .join("");

  wrap.querySelectorAll(".ep-pill").forEach((btn) => {
    btn.addEventListener("click", () => onSelectEp(btn.dataset.ep));
  });
}

function renderChecksBox(title, score, passed, checks, errors) {
  const passTag = passed
    ? `<span class="badge badge-green">通过 · ${fmtScore(score)}</span>`
    : `<span class="badge badge-red">未通过 · ${fmtScore(score)}</span>`;
  const itemsHtml = checks.length
    ? checks
        .map(
          (ck) => `
        <div class="check-item ${ck.passed ? "" : "fail"}">
          <div>
            <div><strong>${esc(ck.label_zh)}</strong></div>
            <div class="check-key">${esc(ck.key)}</div>
          </div>
          <span class="badge ${ck.passed ? "badge-green" : "badge-red"}">${ck.passed ? "✓ 通过" : "✗ 失败"}</span>
        </div>`
        )
        .join("")
    : `<div class="muted-label">该部分无逐项布尔检查明细。</div>`;
  const errHtml = errors && errors.length
    ? `<div class="err-box"><strong>判分报错明细 (${errors.length})：</strong>\n${esc(errors.join("\n"))}</div>`
    : "";
  return `
    <div class="check-box">
      <h4><span>${esc(title)}</span>${passTag}</h4>
      <div class="check-list">${itemsHtml}</div>
      ${errHtml}
    </div>`;
}

export function renderSummaryTab(detail, activeEp) {
  const rows = detail.episodes
    .map((ep) => {
      const ct = ep.contention_telemetry || {};
      const race = ep.race_awareness || {};
      const isCur = ep.ep_name === activeEp.ep_name;
      const raceBadge = race.autonomous_race_aware
        ? `<span class="badge badge-amber">自发感知竞争</span>`
        : `<span class="badge badge-slate">未显式感知</span>`;
      return `
        <tr style="${isCur ? "background:#eff6ff;font-weight:600" : ""}">
          <td>${esc(ep.model_zh)}<div class="muted-label">${esc(ep.mode_zh)}</div></td>
          <td style="font-family:var(--mono)">${fmtScore(ep.mean_score)} (A:${fmtScore(ep.score_a)} / B:${fmtScore(ep.score_b)})</td>
          <td>${ep.joint_pass ? `<span class="badge badge-green">通过</span>` : `<span class="badge badge-red">未通过</span>`}</td>
          <td style="font-family:var(--mono)">${fmtSec(ep.wall_seconds)}</td>
          <td style="font-family:var(--mono)">动 ${ep.gui_action_calls ?? "—"} / 观 ${ep.gui_observation_calls ?? "—"} / CLI ${ep.cli_calls ?? "—"}</td>
          <td style="font-family:var(--mono)">${fmtTokens(ep.input_tokens_total)} / ${fmtTokens(ep.output_tokens_total)}</td>
          <td style="font-family:var(--mono)">${ct.interleaving_role_switches != null ? `切换 ${ct.interleaving_role_switches} · 焦点 ${ct.focus_flips} · 误键 ${ct.misrouted_keystrokes ?? 0}` : "—"}</td>
          <td>${raceBadge}</td>
        </tr>`;
    })
    .join("");

  const g = activeEp.grade || {};
  const roleA = activeEp.actors[0] ? `${activeEp.actors[0].name_zh} (${activeEp.actors[0].role})` : "角色 A";
  const roleB = activeEp.actors[1] ? `${activeEp.actors[1].name_zh} (${activeEp.actors[1].role})` : "角色 B";
  const jointBox =
    (g.subchecks_joint && g.subchecks_joint.length) || (g.errors_joint && g.errors_joint.length)
      ? renderChecksBox("双角色联合耦合检查 (Joint)", g.score_joint, g.joint_pass, g.subchecks_joint || [], g.errors_joint || [])
      : "";

  return `
    <h3 style="margin:0 0 10px">四局评测成绩与交互强度横向对照</h3>
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th>模型与运行模式</th><th>得分（均分 / A / B）</th><th>联合状态</th>
            <th>总耗时</th><th>GUI 动作 / 观察 / CLI</th><th>输入 / 输出 Token</th>
            <th>竞争遥测</th><th>竞争感知</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <h3 style="margin:20px 0 6px">当前局次细粒度判分检查（${esc(activeEp.model_zh)} · ${esc(activeEp.mode_zh)}）</h3>
    <div class="checks-grid">
      ${renderChecksBox(`角色 A：${roleA}`, g.score_a, g.pass_a, g.subchecks_a || [], g.errors_a || [])}
      ${renderChecksBox(`角色 B：${roleB}`, g.score_b, g.pass_b, g.subchecks_b || [], g.errors_b || [])}
      ${jointBox}
    </div>`;
}
