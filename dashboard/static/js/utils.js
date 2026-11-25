const apiCache = new Map();

export async function fetchJson(url) {
  if (apiCache.has(url)) return apiCache.get(url);
  const resp = await fetch(url);
  if (!resp.ok) {
    const msg = await resp.text().catch(() => resp.statusText);
    throw new Error(`请求失败 (${resp.status}): ${msg}`);
  }
  const data = await resp.json();
  apiCache.set(url, data);
  return data;
}

export function esc(val) {
  return String(val ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function fmtScore(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  return Number(v).toFixed(3);
}

export function fmtPct(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  return `${(Number(v) * 100).toFixed(1)}%`;
}

export function fmtDelta(d) {
  if (d === null || d === undefined || Number.isNaN(Number(d))) return "—";
  const num = Number(d);
  const cls = num <= -0.005 ? "delta-neg" : num >= 0.005 ? "delta-pos" : "delta-zero";
  const sign = num > 0 ? "+" : "";
  return `<span class="${cls}">${sign}${(num * 100).toFixed(1)}%</span>`;
}

export function fmtSec(sec) {
  if (sec === null || sec === undefined) return "—";
  const s = Number(sec);
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return `${m}m ${r}s`;
}

export function fmtTokens(n) {
  if (n === null || n === undefined) return "—";
  const v = Number(n);
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}k`;
  return String(v);
}

export function scoreClass(v) {
  if (v === null || v === undefined) return "";
  const n = Number(v);
  if (n >= 0.999) return "sc-perfect";
  if (n >= 0.85) return "sc-high";
  if (n >= 0.65) return "sc-mid";
  return "sc-low";
}

export function showToast(msg) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => el.classList.add("hidden"), 2200);
}

export async function copyText(text, label = "内容") {
  try {
    await navigator.clipboard.writeText(text);
    showToast(`已复制${label}`);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    showToast(`已复制${label}`);
  }
}

/** 轻量安全 Markdown 渲染器（用于渲染角色工单 task.md） */
export function renderMarkdown(md) {
  if (!md) return "<p class='muted-label'>暂无内容</p>";
  const blocks = [];
  const safe = md.replace(/```([\w-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const idx = blocks.length;
    blocks.push(`<pre><code>${esc(code)}</code></pre>`);
    return `@@CODEBLOCK_${idx}@@`;
  });
  const inline = (s) =>
    esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");

  const lines = safe.split("\n");
  let html = "";
  let inUl = false;
  const closeUl = () => {
    if (inUl) {
      html += "</ul>";
      inUl = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      closeUl();
      continue;
    }
    const mBlock = line.match(/^@@CODEBLOCK_(\d+)@@$/);
    if (mBlock) {
      closeUl();
      html += blocks[Number(mBlock[1])];
      continue;
    }
    if (line.startsWith("### ")) {
      closeUl();
      html += `<h3>${inline(line.slice(4))}</h3>`;
    } else if (line.startsWith("## ")) {
      closeUl();
      html += `<h2>${inline(line.slice(3))}</h2>`;
    } else if (line.startsWith("# ")) {
      closeUl();
      html += `<h1>${inline(line.slice(2))}</h1>`;
    } else if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      if (!inUl) {
        html += "<ul>";
        inUl = true;
      }
      html += `<li>${inline(line.replace(/^([-*]|\d+\.)\s+/, ""))}</li>`;
    } else {
      closeUl();
      html += `<p>${inline(line)}</p>`;
    }
  }
  closeUl();
  return html;
}
