import { copyText, esc, renderMarkdown } from "./utils.js";

export function renderContextTab(ctx, mountEl) {
  let layout = "side";
  let activeRole = ctx.roles[0]?.role || "";
  let rawMode = false;

  function renderRoleCard(r) {
    const auditOk = r.permission_audit && (r.permission_audit.verified !== false);
    const mcpHtml = (r.mcp_servers || []).map((m) => `<span class="badge badge-blue">${esc(m)}</span>`).join("");
    const ticketBody = rawMode
      ? `<pre class="code-pre light">${esc(r.ticket_markdown)}</pre>`
      : `<div class="md-view">${renderMarkdown(r.ticket_markdown)}</div>`;

    return `
      <div class="ctx-card">
        <div class="case-card-top">
          <div>
            <strong style="font-size:15px">${esc(r.name_zh)}</strong>
            <code style="margin-left:6px;color:var(--muted)">${esc(r.role)}</code>
          </div>
          <div class="badge-row">
            ${mcpHtml}
            <span class="badge ${auditOk ? "badge-green" : "badge-red"}">${auditOk ? "Non-YOLO 权限核验通过" : "权限待核验"}</span>
          </div>
        </div>
        <p class="case-summary" style="margin:6px 0 8px">${esc(r.brief_zh)}</p>
        <div class="badge-row" style="margin-bottom:8px">
          <span class="badge badge-slate">GUI 驱动：${esc(r.gui_driver)}</span>
          ${r.session_id ? `<span class="badge badge-slate">会话 ID：${esc(r.session_id)}</span>` : ""}
          <span class="badge badge-slate">完整 Prompt：${r.prompt_char_count} 字符</span>
          <span class="badge badge-slate">工单来源：${esc(r.ticket_source_episode)}</span>
        </div>

        <div class="ctx-block-title">
          <span>① 系统运行环境提示头（Runner 注入）</span>
          <button class="btn-ghost copy-btn" data-copy="full" data-role="${esc(r.role)}">复制完整模型 Prompt</button>
        </div>
        <div class="muted-label" style="margin-bottom:6px">${esc(r.runner_note_zh)}</div>
        <pre class="code-pre">${esc(r.system_prefix)}</pre>

        <div class="ctx-block-title">
          <span>② 模型收到的角色任务工单（tickets/${esc(r.role)}/task.md）</span>
          <button class="btn-ghost copy-btn" data-copy="ticket" data-role="${esc(r.role)}">复制工单原文</button>
        </div>
        ${ticketBody}

        ${
          r.permission_audit
            ? `<details class="fold-box">
                <summary>查看 Non-YOLO 权限审计凭证（permission-audit-verified.json）</summary>
                <pre class="code-pre light">${esc(JSON.stringify(r.permission_audit, null, 2))}</pre>
              </details>`
            : ""
        }
      </div>`;
  }

  function draw() {
    const visibleRoles = layout === "side" ? ctx.roles : ctx.roles.filter((r) => r.role === activeRole);
    const roleButtons =
      layout === "single"
        ? `<div class="segmented">
            ${ctx.roles
              .map(
                (r) =>
                  `<button class="seg-btn ${r.role === activeRole ? "active" : ""}" data-pick-role="${esc(r.role)}">${esc(r.name_zh)}</button>`
              )
              .join("")}
          </div>`
        : "";

    const serviceBlock = ctx.service_state
      ? `<details class="fold-box" style="margin-top:16px">
          <summary>查看初始桌面环境与服务状态快照（service_state.json）</summary>
          <pre class="code-pre light">${esc(JSON.stringify(ctx.service_state, null, 2))}</pre>
        </details>`
      : "";

    mountEl.innerHTML = `
      <div class="ctx-toolbar">
        <div>
          <h3 style="margin:0">模型实际接收的任务上下文（Task Context）</h3>
          <div class="muted-label">包含注入给 Codex 的系统环境与 MCP 工具声明 + 完整角色工单正文；共 ${ctx.roles.length} 个并发角色。</div>
        </div>
        <div class="badge-row">
          <div class="segmented">
            <button class="seg-btn ${layout === "side" ? "active" : ""}" data-layout="side">双角色并排对照</button>
            <button class="seg-btn ${layout === "single" ? "active" : ""}" data-layout="single">单角色宽屏阅读</button>
          </div>
          ${roleButtons}
          <button class="btn-ghost" id="toggleRawTicket">${rawMode ? "切换 Markdown 渲染" : "切换工单纯文本"}</button>
        </div>
      </div>
      <div class="ctx-grid ${layout === "side" ? "side-by-side" : ""}">
        ${visibleRoles.map(renderRoleCard).join("")}
      </div>
      ${serviceBlock}`;

    mountEl.querySelectorAll("[data-layout]").forEach((btn) => {
      btn.addEventListener("click", () => {
        layout = btn.dataset.layout;
        draw();
      });
    });
    mountEl.querySelectorAll("[data-pick-role]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeRole = btn.dataset.pickRole;
        draw();
      });
    });
    mountEl.querySelector("#toggleRawTicket")?.addEventListener("click", () => {
      rawMode = !rawMode;
      draw();
    });
    mountEl.querySelectorAll(".copy-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const r = ctx.roles.find((x) => x.role === btn.dataset.role);
        if (!r) return;
        if (btn.dataset.copy === "full") copyText(r.full_prompt, `${r.name_zh} 完整 Prompt`);
        else copyText(r.ticket_markdown, `${r.name_zh} 角色工单`);
      });
    });
  }

  draw();
}
