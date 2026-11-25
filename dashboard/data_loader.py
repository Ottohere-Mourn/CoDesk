# -*- coding: utf-8 -*-
"""精选 23 题与 92 局 / 184 角色轨迹数据加载与结构化解析器。"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any

from dashboard.catalog_zh import (
    BATCH_META,
    CASE_CATALOG_ZH,
    DOMAIN_META,
    MECHANISM_META,
    MODE_ZH,
    MODEL_ZH,
    translate_check_key,
    translate_tool_name,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "lists" / "curated_23cases_and_trajectories_20261125.json"

GUI_OBS_TOOLS = {
    "get_state",
    "get_screenshot",
    "get_ax_state",
    "get_ax_state_and_screenshot",
    "screenshot",
}


def _safe_read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _safe_parse_jsonl_line(line: str) -> dict[str, Any] | None:
    raw = line.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 处理脱敏替换 <BASE64_OMITTED:...> 邻接反斜杠导致的个别转义异常
        fixed = re.sub(r'\\(?=<BASE64_OMITTED:)', r'\\\\', raw)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return {"type": "raw_line", "raw_text": raw[:2000]}


def _classify_tool_channel(tool_name: str, server: str = "") -> str:
    low = (tool_name or "").lower()
    srv = (server or "").lower()
    short = low.split(".")[-1]
    if "guest_bash" in low or srv == "guest_bash" or short == "command_execution":
        return "cli"
    if short in GUI_OBS_TOOLS:
        return "gui_obs"
    if srv in ("qwen_cua_driver", "desktop") or "qwen_cua" in low or low.startswith("desktop."):
        return "gui_act"
    return "other"


def _parse_episode_name(ep_name: str) -> tuple[str, str]:
    if ep_name.startswith("isolated_"):
        mode = "isolated"
        raw_model = ep_name[len("isolated_"):]
    elif ep_name.startswith("seq_ab_"):
        mode = "seq_ab"
        raw_model = ep_name[len("seq_ab_"):]
    elif ep_name.startswith("shared_"):
        mode = "shared"
        raw_model = ep_name[len("shared_"):]
    else:
        mode = "unknown"
        raw_model = ep_name
    model = "gpt-6.1-sol" if raw_model in ("gpt-6_1-sol", "gpt-6.1-sol") else raw_model
    return mode, model


def _extract_role_order(ep_dir: Path, report: dict[str, Any] | None) -> list[str]:
    roles: list[str] = []
    if report:
        ct = report.get("contention_telemetry") or {}
        if isinstance(ct.get("roles"), list) and ct["roles"]:
            roles = [str(r) for r in ct["roles"]]
        elif isinstance(report.get("actors"), dict) and report["actors"]:
            roles = [str(r) for r in report["actors"].keys()]
    if not roles:
        roles = sorted(
            p.name[len("actor_"):]
            for p in ep_dir.iterdir()
            if p.is_dir() and p.name.startswith("actor_")
        )
    return roles


def _reconstruct_prompt_parts(
    case_id: str,
    batch: str,
    role: str,
    gui_driver: str,
    ticket_md: str,
) -> dict[str, Any]:
    b = "`"
    sess_id = f"s_{role[:10]}"
    if case_id in ("EC-01", "EC-03"):
        wrapper = (
            f"You are operating a Linux engineering workstation (1280x720 normalized display view, workspace {b}/workspace{b}, time budget: 7200s).\n"
            "You have full access to both GUI desktop interaction tools and workstation shell commands.\n\n"
        )
        runner_note = "EC-v1 / Curated-8 经典双智能体封装（desktop 1280×720 归一化坐标 + guest_bash）"
    elif batch == "Curated-8":
        wrapper = (
            f"Workstation environment (1920x1080 Linux desktop, workspace {b}/workspace{b}):\n"
            "- Use the Desktop GUI MCP tools to inspect and interact with live desktop windows.\n"
            f"- Use {b}guest_bash{b} to run shell commands, scripts, compilers, and local tools in {b}/workspace{b}.\n"
            "- Save any edits made inside open desktop applications before finishing.\n\n"
        )
        runner_note = "Curated-8 中性无步数上限运行提示头（qwen_cua_driver 1920×1080 + guest_bash）"
    elif batch.startswith("AW-v1"):
        if gui_driver == "qwen_cua":
            drv_line = (
                f"- Desktop GUI MCP server: {b}qwen_cua_driver{b} (pass {b}session={json.dumps(sess_id)}{b} where supported). "
                f"Use {b}get_state{b} to list open desktop windows, {b}get_ax_state_and_screenshot{b} / {b}get_screenshot{b} to inspect live applications on the 1920x1080 display, and act via {b}click{b}, {b}drag{b}, {b}type_text{b}, {b}press_key{b}, {b}hotkey{b}, etc.\n"
            )
        else:
            drv_line = f"- Desktop GUI MCP server: {b}desktop{b} (1280x720 normalized screen coordinates).\n"
        wrapper = (
            f"Workstation runtime notes (Linux 1920x1080 desktop + CLI workspace {b}/workspace{b}):\n"
            f"{drv_line}"
            f"- Workstation shell MCP tool: {b}guest_bash{b} (executes Linux CLI commands, Python, SQLite, GDAL/OGR, FreeCADCmd, Inkscape CLI, LibreOffice headless, lrelease, ffmpeg, git, and localhost HTTP calls in {b}/workspace{b}; {b}/home/user/Downloads{b} is mounted read-only; interact with and verify live desktop GUI windows via the Desktop GUI MCP server).\n\n"
        )
        runner_note = "AW-v1 真实工作站 2h 无上限运行提示头（X11 隔离 CLI 容器 + qwen_cua_driver GUI）"
    else:
        if gui_driver == "qwen_cua":
            drv_line = (
                f"- Desktop GUI MCP server: {b}qwen_cua_driver{b} (pass {b}session={json.dumps(sess_id)}{b} where supported). "
                "Use it to inspect and operate live desktop windows (browsers, LibreOffice, Blender, dialogs).\n"
            )
        else:
            drv_line = f"- Desktop GUI MCP server: {b}desktop{b} (1280x720 normalized screen coordinates).\n"
        wrapper = (
            f"Workstation runtime notes (1920x1080 Linux desktop, workspace {b}/workspace{b}):\n"
            f"{drv_line}"
            f"- Headless workstation shell MCP tool: {b}guest_bash{b} (runs in {b}/workspace{b} with Python, compilers, document/CAD CLI utilities, and local network access; GUI/X11 operations must go through the Desktop GUI MCP server, and any edits in open GUI windows must be saved before finishing).\n\n"
        )
        runner_note = f"{batch} 原生桌面无步数上限运行提示头（无头 guest_bash + qwen_cua_driver GUI）"

    return {
        "system_prefix": wrapper.rstrip(),
        "ticket_markdown": ticket_md,
        "full_prompt": f"{wrapper}{ticket_md}\n",
        "runner_note_zh": runner_note,
        "gui_driver": gui_driver,
        "session_id": sess_id if gui_driver == "qwen_cua" else None,
        "mcp_servers": (
            ["qwen_cua_driver", "guest_bash"] if gui_driver == "qwen_cua" else ["desktop", "guest_bash"]
        ),
    }


def _format_grade_detail(grade: dict[str, Any] | None) -> dict[str, Any]:
    if not grade:
        return {
            "score_a": None,
            "score_b": None,
            "score_joint": None,
            "mean_score": None,
            "pass_a": None,
            "pass_b": None,
            "joint_pass": None,
            "subchecks_a": [],
            "subchecks_b": [],
            "subchecks_joint": [],
            "errors_a": [],
            "errors_b": [],
            "errors_joint": [],
        }

    def _pack_checks(raw_checks: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_checks, dict):
            return []
        out = []
        for k, v in raw_checks.items():
            out.append({
                "key": str(k),
                "label_zh": translate_check_key(str(k)),
                "passed": bool(v),
                "raw_value": v,
            })
        return out

    return {
        "score_a": grade.get("score_a"),
        "score_b": grade.get("score_b"),
        "score_joint": grade.get("score_joint"),
        "mean_score": grade.get("mean_score"),
        "pass_a": grade.get("pass_a"),
        "pass_b": grade.get("pass_b"),
        "joint_pass": grade.get("joint_pass"),
        "subchecks_a": _pack_checks(grade.get("subchecks_a")),
        "subchecks_b": _pack_checks(grade.get("subchecks_b")),
        "subchecks_joint": _pack_checks(grade.get("subchecks_joint")),
        "errors_a": list(grade.get("errors_a") or []),
        "errors_b": list(grade.get("errors_b") or []),
        "errors_joint": list(grade.get("errors_joint") or []),
    }


def _summarize_episode(case_id: str, ep_dir: Path) -> dict[str, Any]:
    mode, model = _parse_episode_name(ep_dir.name)
    report = _safe_read_json(ep_dir / "report.json") or {}
    grade = _safe_read_json(ep_dir / "grade.json") or report.get("grade") or {}
    roles = _extract_role_order(ep_dir, report)
    zh_case = CASE_CATALOG_ZH.get(case_id, {})
    roles_zh_map = zh_case.get("roles_zh", {})

    actors_raw = report.get("actors") if isinstance(report.get("actors"), dict) else {}
    actors_list: list[dict[str, Any]] = []
    total_in_tok = report.get("input_tokens_total")
    total_out_tok = report.get("output_tokens_total")
    gui_driver = report.get("gui_driver")

    for r in roles:
        actor_dir = ep_dir / f"actor_{r}"
        asum = _safe_read_json(actor_dir / "actor_summary.json") or actors_raw.get(r) or {}
        audit = _safe_read_json(actor_dir / "permission-audit-verified.json") or {}
        usage = asum.get("usage") if isinstance(asum.get("usage"), dict) else {}
        if not gui_driver:
            gui_driver = asum.get("gui_driver")
        r_meta = roles_zh_map.get(r, {})
        actors_list.append({
            "role": r,
            "name_zh": r_meta.get("name_zh", r),
            "brief_zh": r_meta.get("brief_zh", ""),
            "status": asum.get("status", "done"),
            "wall_seconds": asum.get("wall_seconds"),
            "permission_audit_ok": asum.get("permission_audit_ok", bool(audit.get("verified", True))),
            "gui_driver": asum.get("gui_driver") or ("desktop" if case_id in ("EC-01", "EC-03") else "qwen_cua"),
            "gui_action_calls": asum.get("gui_action_calls", 0),
            "gui_observation_calls": asum.get("gui_observation_calls", 0),
            "cli_calls": asum.get("cli_calls", 0),
            "input_tokens": usage.get("input_tokens"),
            "cached_input_tokens": usage.get("cached_input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "reasoning_output_tokens": usage.get("reasoning_output_tokens"),
            "has_actions": (actor_dir / "actions.jsonl").exists(),
            "has_codex_events": (actor_dir / "codex_events.jsonl").exists(),
        })

    if not gui_driver:
        gui_driver = "desktop" if case_id in ("EC-01", "EC-03") else "qwen_cua"

    ct = report.get("contention_telemetry")
    race = report.get("race_awareness")

    score_a = grade.get("score_a", report.get("score_a"))
    score_b = grade.get("score_b", report.get("score_b"))
    mean_score = grade.get("mean_score", report.get("mean_score"))
    if mean_score is None and score_a is not None and score_b is not None:
        mean_score = round((float(score_a) + float(score_b)) / 2.0, 4)
    if mean_score is None and report.get("pass_a") is not None and report.get("pass_b") is not None:
        mean_score = round(((1.0 if report["pass_a"] else 0.0) + (1.0 if report["pass_b"] else 0.0)) / 2.0, 4)

    return {
        "ep_name": ep_dir.name,
        "mode": mode,
        "mode_zh": MODE_ZH.get(mode, mode),
        "model": model,
        "model_zh": MODEL_ZH.get(model, model),
        "gui_driver": gui_driver,
        "wall_seconds": report.get("wall_seconds"),
        "score_a": score_a,
        "score_b": score_b,
        "mean_score": mean_score,
        "pass_a": grade.get("pass_a", report.get("pass_a")),
        "pass_b": grade.get("pass_b", report.get("pass_b")),
        "joint_pass": grade.get("joint_pass", report.get("joint_pass")),
        "gui_action_calls": report.get("gui_action_calls"),
        "gui_observation_calls": report.get("gui_observation_calls"),
        "cli_calls": report.get("cli_calls"),
        "input_tokens_total": total_in_tok,
        "output_tokens_total": total_out_tok,
        "has_shared_timeline": (ep_dir / "shared_timeline.json").exists(),
        "contention_telemetry": ct,
        "race_awareness": race,
        "actors": actors_list,
        "grade": _format_grade_detail(grade),
    }


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_overview_payload() -> dict[str, Any]:
    manifest = load_manifest()
    cases_out: list[dict[str, Any]] = []
    software_counts: dict[str, int] = {}

    for c in manifest["cases"]:
        cid = c["id"]
        batch = c["batch"]
        zh = CASE_CATALOG_ZH.get(cid, {})
        tdir = REPO_ROOT / c["trajectory_dir"]

        sol_b = c["gpt-6.1-sol"]["baseline"]["mean_score"]
        sol_s = c["gpt-6.1-sol"]["shared"]["mean_score"]
        ast_b = c["gpt-6-astra"]["baseline"]["mean_score"]
        ast_s = c["gpt-6-astra"]["shared"]["mean_score"]
        sol_delta = round(sol_s - sol_b, 4)
        ast_delta = round(ast_s - ast_b, 4)
        worst_drop = round(min(sol_delta, ast_delta), 4)

        if sol_s >= 0.9999 and ast_s >= 0.9999:
            sensitivity_cat = "saturated"
            sensitivity_zh = "双模型共享全满分"
        elif worst_drop <= -0.05:
            sensitivity_cat = "strong_drop"
            sensitivity_zh = "显著共享退化 (Δ≤-5%)"
        else:
            sensitivity_cat = "nonsat_mild"
            sensitivity_zh = "非饱和区分题"

        # 读取两局 shared 的核心遥测指标用于总览展示
        shared_metrics: dict[str, Any] = {}
        domain_en = ""
        roles_meta: list[dict[str, str]] = []
        for ep_name in c.get("episode_dirs", []):
            ep_dir = tdir / ep_name
            mode, model = _parse_episode_name(ep_name)
            if mode == "shared" and ep_dir.exists():
                rep = _safe_read_json(ep_dir / "report.json") or {}
                if not domain_en:
                    domain_en = rep.get("domain", "")
                if not roles_meta:
                    for r in _extract_role_order(ep_dir, rep):
                        rm = zh.get("roles_zh", {}).get(r, {})
                        roles_meta.append({
                            "role": r,
                            "name_zh": rm.get("name_zh", r),
                            "brief_zh": rm.get("brief_zh", ""),
                        })
                ct = rep.get("contention_telemetry") or {}
                race = rep.get("race_awareness") or {}
                shared_metrics[model] = {
                    "wall_seconds": rep.get("wall_seconds"),
                    "gui_action_calls": rep.get("gui_action_calls"),
                    "gui_observation_calls": rep.get("gui_observation_calls"),
                    "cli_calls": rep.get("cli_calls"),
                    "interleaving_role_switches": ct.get("interleaving_role_switches"),
                    "focus_flips": ct.get("focus_flips"),
                    "misrouted_keystrokes": ct.get("misrouted_keystrokes"),
                    "clipboard_changes": ct.get("clipboard_changes"),
                    "overlap_seconds": ct.get("overlap_seconds"),
                    "autonomous_race_aware": race.get("autonomous_race_aware"),
                }

        sw_stack = list(zh.get("software_stack", []))
        for sw in sw_stack:
            software_counts[sw] = software_counts.get(sw, 0) + 1

        mech_id = zh.get("mechanism", "office_uno")
        dom_id = zh.get("domain_cat", "hardware_research_media")
        cases_out.append({
            "id": cid,
            "batch": batch,
            "batch_short": BATCH_META.get(batch, {}).get("short", batch),
            "batch_label": BATCH_META.get(batch, {}).get("label", batch),
            "title_en": c["title"],
            "title_zh": zh.get("title_zh", c["title"]),
            "summary_zh": zh.get("summary_zh", ""),
            "contention_zh": zh.get("contention_zh", ""),
            "domain_en": domain_en,
            "domain_cat": dom_id,
            "domain_label": DOMAIN_META.get(dom_id, {}).get("label", dom_id),
            "mechanism": mech_id,
            "mechanism_label": MECHANISM_META.get(mech_id, {}).get("label", mech_id),
            "mechanism_short": MECHANISM_META.get(mech_id, {}).get("short", mech_id),
            "software_stack": sw_stack,
            "roles": roles_meta,
            "source_file": c["source_file"],
            "runner_file": c["runner_file"],
            "trajectory_dir": c["trajectory_dir"],
            "episode_dirs": c["episode_dirs"],
            "sensitivity_cat": sensitivity_cat,
            "sensitivity_zh": sensitivity_zh,
            "sol": {
                "baseline": c["gpt-6.1-sol"]["baseline"],
                "shared": c["gpt-6.1-sol"]["shared"],
                "delta": sol_delta,
            },
            "astra": {
                "baseline": c["gpt-6-astra"]["baseline"],
                "shared": c["gpt-6-astra"]["shared"],
                "delta": ast_delta,
            },
            "worst_drop": worst_drop,
            "model_gap_shared": round(ast_s - sol_s, 4),
            "shared_metrics": shared_metrics,
        })

    # 计算 17 题非饱和子集均分
    nonsat = [x for x in cases_out if x["sensitivity_cat"] != "saturated"]
    nonsat_summary = {
        "count": len(nonsat),
        "sol_baseline_mean": round(sum(x["sol"]["baseline"]["mean_score"] for x in nonsat) / max(len(nonsat), 1), 4),
        "sol_shared_mean": round(sum(x["sol"]["shared"]["mean_score"] for x in nonsat) / max(len(nonsat), 1), 4),
        "astra_baseline_mean": round(sum(x["astra"]["baseline"]["mean_score"] for x in nonsat) / max(len(nonsat), 1), 4),
        "astra_shared_mean": round(sum(x["astra"]["shared"]["mean_score"] for x in nonsat) / max(len(nonsat), 1), 4),
    }

    # 按批次、机制、领域聚合统计
    def _agg(field: str, meta_map: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
        buckets: dict[str, list[dict[str, Any]]] = {}
        for item in cases_out:
            buckets.setdefault(item[field], []).append(item)
        rows = []
        for key, meta in meta_map.items():
            items = buckets.get(key, [])
            if not items:
                continue
            n = len(items)
            sol_b = sum(i["sol"]["baseline"]["mean_score"] for i in items) / n
            sol_s = sum(i["sol"]["shared"]["mean_score"] for i in items) / n
            ast_b = sum(i["astra"]["baseline"]["mean_score"] for i in items) / n
            ast_s = sum(i["astra"]["shared"]["mean_score"] for i in items) / n
            rows.append({
                "key": key,
                "label": meta.get("label", key),
                "short": meta.get("short", key),
                "color": meta.get("color", "#2563eb"),
                "desc": meta.get("desc", ""),
                "count": n,
                "sol_baseline": round(sol_b, 4),
                "sol_shared": round(sol_s, 4),
                "sol_delta": round(sol_s - sol_b, 4),
                "astra_baseline": round(ast_b, 4),
                "astra_shared": round(ast_s, 4),
                "astra_delta": round(ast_s - ast_b, 4),
            })
        return rows

    top_software = sorted(software_counts.items(), key=lambda kv: (-kv[1], kv[0]))

    return {
        "suite": manifest["suite"],
        "date": manifest["date"],
        "total_cases": manifest["total_cases"],
        "total_episodes": manifest["total_episodes"],
        "total_agent_trajectories": manifest["total_agent_trajectories"],
        "models": manifest["models"],
        "reasoning_effort": manifest["reasoning_effort"],
        "overall_summary": manifest["overall_summary"],
        "nonsat_summary": nonsat_summary,
        "taxonomy": {
            "batches": _agg("batch", BATCH_META),
            "mechanisms": _agg("mechanism", MECHANISM_META),
            "domains": _agg("domain_cat", DOMAIN_META),
            "sensitivity": [
                {
                    "key": "strong_drop",
                    "label": "显著共享退化 (Δ≤-5%)",
                    "count": sum(1 for x in cases_out if x["sensitivity_cat"] == "strong_drop"),
                    "color": "#dc2626",
                },
                {
                    "key": "nonsat_mild",
                    "label": "非饱和区分题",
                    "count": sum(1 for x in cases_out if x["sensitivity_cat"] == "nonsat_mild"),
                    "color": "#d97706",
                },
                {
                    "key": "saturated",
                    "label": "双模型共享全满分",
                    "count": sum(1 for x in cases_out if x["sensitivity_cat"] == "saturated"),
                    "color": "#059669",
                },
            ],
            "software": [{"name": k, "count": v} for k, v in top_software],
        },
        "cases": cases_out,
    }


@lru_cache(maxsize=32)
def get_case_detail(case_id: str) -> dict[str, Any] | None:
    overview = get_overview_payload()
    case_summary = next((c for c in overview["cases"] if c["id"] == case_id), None)
    if not case_summary:
        return None

    cdir = REPO_ROOT / case_summary["trajectory_dir"]
    episodes: list[dict[str, Any]] = []
    # 按固定语义排序：Sol 共享 -> Astra 共享 -> Sol 基线 -> Astra 基线
    order_key = {
        ("shared", "gpt-6.1-sol"): 0,
        ("shared", "gpt-6-astra"): 1,
        ("isolated", "gpt-6.1-sol"): 2,
        ("seq_ab", "gpt-6.1-sol"): 2,
        ("isolated", "gpt-6-astra"): 3,
        ("seq_ab", "gpt-6-astra"): 3,
    }
    for ep_name in case_summary["episode_dirs"]:
        ep_dir = cdir / ep_name
        if ep_dir.exists():
            episodes.append(_summarize_episode(case_id, ep_dir))
    episodes.sort(key=lambda e: order_key.get((e["mode"], e["model"]), 9))

    return {
        "case": case_summary,
        "episodes": episodes,
    }


@lru_cache(maxsize=128)
def get_episode_context(case_id: str, ep_name: str) -> dict[str, Any] | None:
    detail = get_case_detail(case_id)
    if not detail:
        return None
    case_meta = detail["case"]
    ep_meta = next((e for e in detail["episodes"] if e["ep_name"] == ep_name), None)
    if not ep_meta:
        return None

    cdir = REPO_ROOT / case_meta["trajectory_dir"]
    ep_dir = cdir / ep_name
    # 若 isolated 局次未重复落盘 tickets，则从同题 shared 局次读取原始工单
    tickets_root = ep_dir / "tickets"
    ticket_source = ep_name
    if not tickets_root.exists():
        for cand in sorted(cdir.iterdir()):
            if cand.is_dir() and (cand / "tickets").exists():
                tickets_root = cand / "tickets"
                ticket_source = cand.name
                break

    service_state = _safe_read_json(ep_dir / "service_state.json")
    if service_state is None and ticket_source != ep_name:
        service_state = _safe_read_json(cdir / ticket_source / "service_state.json")

    roles_ctx: list[dict[str, Any]] = []
    for actor in ep_meta["actors"]:
        role = actor["role"]
        tk_path = tickets_root / role / "task.md"
        ticket_md = tk_path.read_text(encoding="utf-8", errors="replace") if tk_path.exists() else ""
        audit = _safe_read_json(ep_dir / f"actor_{role}" / "permission-audit-verified.json")
        prompt_parts = _reconstruct_prompt_parts(
            case_id=case_id,
            batch=case_meta["batch"],
            role=role,
            gui_driver=actor["gui_driver"],
            ticket_md=ticket_md,
        )
        roles_ctx.append({
            "role": role,
            "name_zh": actor["name_zh"],
            "brief_zh": actor["brief_zh"],
            "ticket_source_episode": ticket_source,
            "ticket_char_count": len(ticket_md),
            "prompt_char_count": len(prompt_parts["full_prompt"]),
            "permission_audit": audit,
            **prompt_parts,
        })

    return {
        "case_id": case_id,
        "ep_name": ep_name,
        "mode": ep_meta["mode"],
        "mode_zh": ep_meta["mode_zh"],
        "model": ep_meta["model"],
        "model_zh": ep_meta["model_zh"],
        "service_state": service_state,
        "roles": roles_ctx,
    }


@lru_cache(maxsize=128)
def get_episode_timeline(case_id: str, ep_name: str) -> dict[str, Any] | None:
    detail = get_case_detail(case_id)
    if not detail:
        return None
    case_meta = detail["case"]
    ep_meta = next((e for e in detail["episodes"] if e["ep_name"] == ep_name), None)
    if not ep_meta:
        return None

    ep_dir = REPO_ROOT / case_meta["trajectory_dir"] / ep_name
    role_zh_map = {a["role"]: a["name_zh"] for a in ep_meta["actors"]}
    tl_path = ep_dir / "shared_timeline.json"
    raw_events: list[dict[str, Any]] = []
    source = "shared_timeline.json"

    if tl_path.exists():
        loaded = _safe_read_json(tl_path)
        if isinstance(loaded, list):
            raw_events = loaded
    if not raw_events:
        source = "actions.jsonl_merged"
        for actor in ep_meta["actors"]:
            ap = ep_dir / f"actor_{actor['role']}" / "actions.jsonl"
            if ap.exists():
                for ln in ap.read_text(encoding="utf-8", errors="replace").splitlines():
                    obj = _safe_parse_jsonl_line(ln)
                    if obj and obj.get("type") != "raw_line":
                        obj.setdefault("role", actor["role"])
                        raw_events.append(obj)
        raw_events.sort(key=lambda x: float(x.get("start_wall") or x.get("timestamp") or 0.0))

    t0 = None
    for ev in raw_events:
        ts = ev.get("start_wall") or ev.get("timestamp")
        if ts is not None:
            t0 = float(ts)
            break
    if t0 is None:
        t0 = 0.0

    events_out: list[dict[str, Any]] = []
    prev_role = None
    prev_win = None
    role_switches = 0
    focus_flips = 0
    clipboard_changes = 0
    pointer_moves = 0
    max_rel_s = 0.0

    for idx, ev in enumerate(raw_events):
        role = str(ev.get("role", "unknown"))
        tool = str(ev.get("tool") or ev.get("raw_tool") or "")
        server = str(ev.get("server") or "")
        ts = float(ev.get("start_wall") or ev.get("timestamp") or t0)
        rel_s = round(max(0.0, ts - t0), 2)
        dur_s = round(float(ev.get("duration_s") or 0.0), 3)
        if rel_s + dur_s > max_rel_s:
            max_rel_s = rel_s + dur_s

        win_before = ev.get("win_before") or ""
        win_after = ev.get("win_after") or ""
        is_switch = prev_role is not None and role != prev_role
        if is_switch:
            role_switches += 1
        is_focus_flip = bool(
            (win_before and win_after and win_before != win_after)
            or (prev_win and win_before and prev_win != win_before)
        )
        if is_focus_flip:
            focus_flips += 1
        is_clip = bool(ev.get("clipboard_changed"))
        if is_clip:
            clipboard_changes += 1
        is_ptr = bool(ev.get("pointer_moved"))
        if is_ptr:
            pointer_moves += 1

        args = ev.get("args") or {}
        if isinstance(args, dict) and "command" in args:
            preview = str(args["command"]).replace("\n", " ")[:180]
        else:
            preview = json.dumps(args, ensure_ascii=False)[:180]

        events_out.append({
            "idx": idx + 1,
            "role": role,
            "role_zh": role_zh_map.get(role, role),
            "rel_s": rel_s,
            "duration_s": dur_s,
            "tool": tool,
            "tool_zh": translate_tool_name(tool),
            "channel": _classify_tool_channel(tool, server),
            "win_before": win_before,
            "win_after": win_after,
            "is_role_switch": is_switch,
            "is_focus_flip": is_focus_flip,
            "clipboard_changed": is_clip,
            "pointer_moved": is_ptr,
            "args_preview": preview,
            "args": args,
        })
        prev_role = role
        if win_after:
            prev_win = win_after

    return {
        "case_id": case_id,
        "ep_name": ep_name,
        "source": source,
        "roles": [{"role": a["role"], "name_zh": a["name_zh"]} for a in ep_meta["actors"]],
        "total_events": len(events_out),
        "duration_span_s": round(max_rel_s, 2),
        "computed_stats": {
            "role_switches": role_switches,
            "focus_flips": focus_flips,
            "clipboard_changes": clipboard_changes,
            "pointer_moves": pointer_moves,
        },
        "telemetry": ep_meta.get("contention_telemetry"),
        "race_awareness": ep_meta.get("race_awareness"),
        "events": events_out,
    }


def _clean_mcp_result(result: Any) -> dict[str, Any]:
    """抽取 MCP 返回内容，保留全部文本/无障碍树/错误，并将 Base64 占位符显式标注。"""
    text_parts: list[str] = []
    base64_notes: list[str] = []
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            for blk in content:
                if not isinstance(blk, dict):
                    text_parts.append(str(blk))
                    continue
                btype = blk.get("type", "")
                if btype == "text":
                    txt = str(blk.get("text", ""))
                    for m in re.findall(r"<BASE64_OMITTED:[^>]+>", txt):
                        base64_notes.append(m)
                    text_parts.append(txt)
                elif btype == "image":
                    data_val = str(blk.get("data", ""))
                    if "BASE64_OMITTED" in data_val:
                        base64_notes.append(data_val)
                    else:
                        base64_notes.append(f"<IMAGE:{blk.get('mimeType', 'image/png')}>")
                else:
                    text_parts.append(json.dumps(blk, ensure_ascii=False))
        elif "structured_content" in result and result["structured_content"] is not None:
            text_parts.append(json.dumps(result["structured_content"], ensure_ascii=False, indent=2))
        else:
            text_parts.append(json.dumps(result, ensure_ascii=False, indent=2))
    elif result is not None:
        text_parts.append(str(result))

    joined = "\n".join(p for p in text_parts if p)
    return {
        "text": joined,
        "base64_omitted": base64_notes,
    }


@lru_cache(maxsize=128)
def get_actor_trajectory(case_id: str, ep_name: str, role: str) -> dict[str, Any] | None:
    detail = get_case_detail(case_id)
    if not detail:
        return None
    case_meta = detail["case"]
    ep_meta = next((e for e in detail["episodes"] if e["ep_name"] == ep_name), None)
    if not ep_meta:
        return None
    actor_meta = next((a for a in ep_meta["actors"] if a["role"] == role), None)
    if not actor_meta:
        return None

    actor_dir = REPO_ROOT / case_meta["trajectory_dir"] / ep_name / f"actor_{role}"
    ev_path = actor_dir / "codex_events.jsonl"
    act_path = actor_dir / "actions.jsonl"

    # 读取 actions.jsonl 作为时间戳与窗口焦点映射补充
    actions_rows: list[dict[str, Any]] = []
    if act_path.exists():
        for ln in act_path.read_text(encoding="utf-8", errors="replace").splitlines():
            obj = _safe_parse_jsonl_line(ln)
            if obj and obj.get("type") != "raw_line":
                actions_rows.append(obj)

    steps_by_id: dict[str, dict[str, Any]] = {}
    ordered_steps: list[dict[str, Any]] = []
    turn_usages: list[dict[str, Any]] = []
    counts = {
        "reasoning": 0,
        "agent_message": 0,
        "cli": 0,
        "gui_obs": 0,
        "gui_act": 0,
        "other": 0,
    }

    if ev_path.exists():
        for line_no, ln in enumerate(ev_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            ev = _safe_parse_jsonl_line(ln)
            if not ev:
                continue
            etype = ev.get("type")
            if etype == "turn.completed":
                usage = ev.get("usage")
                if isinstance(usage, dict):
                    turn_usages.append(usage)
                continue
            if etype == "error":
                ordered_steps.append({
                    "step_no": len(ordered_steps) + 1,
                    "item_id": f"err_{line_no}",
                    "kind": "other",
                    "kind_zh": "运行时错误事件",
                    "title": "Codex 运行错误 (Error)",
                    "text": str(ev.get("message") or json.dumps(ev, ensure_ascii=False)),
                    "error": ev.get("message") or ev,
                    "status": "failed",
                })
                counts["other"] += 1
                continue
            if etype == "raw_line":
                ordered_steps.append({
                    "step_no": len(ordered_steps) + 1,
                    "item_id": f"raw_{line_no}",
                    "kind": "other",
                    "kind_zh": "原始日志行",
                    "title": f"日志第 {line_no} 行（含转义截断）",
                    "text": ev.get("raw_text", ""),
                    "status": "parsed_fallback",
                })
                counts["other"] += 1
                continue
            if etype not in ("item.started", "item.completed", "item.updated"):
                continue

            item = ev.get("item")
            if not isinstance(item, dict):
                continue
            iid = str(item.get("id") or f"line_{line_no}")
            itype = str(item.get("type") or "unknown")

            if itype == "reasoning":
                rec = steps_by_id.get(iid)
                if rec is None:
                    rec = {
                        "step_no": len(ordered_steps) + 1,
                        "item_id": iid,
                        "kind": "reasoning",
                        "kind_zh": "模型推理思考",
                        "title": "内部推理链 (Reasoning)",
                        "text": item.get("text", ""),
                        "status": "completed",
                    }
                    steps_by_id[iid] = rec
                    ordered_steps.append(rec)
                    counts["reasoning"] += 1
                else:
                    rec["text"] = item.get("text", rec["text"])

            elif itype == "agent_message":
                rec = steps_by_id.get(iid)
                if rec is None:
                    rec = {
                        "step_no": len(ordered_steps) + 1,
                        "item_id": iid,
                        "kind": "agent_message",
                        "kind_zh": "智能体回复/汇报",
                        "title": "智能体文本消息",
                        "text": item.get("text", ""),
                        "status": "completed",
                    }
                    steps_by_id[iid] = rec
                    ordered_steps.append(rec)
                    counts["agent_message"] += 1
                else:
                    rec["text"] = item.get("text", rec["text"])

            elif itype == "mcp_tool_call":
                server = str(item.get("server") or "")
                tool = str(item.get("tool") or "")
                full_tool = f"{server}.{tool}" if server and not tool.startswith(server) else tool
                chan = _classify_tool_channel(full_tool, server)
                kind_zh_map = {
                    "cli": "终端命令 (CLI)",
                    "gui_obs": "桌面观察 (GUI Obs)",
                    "gui_act": "桌面操作 (GUI Act)",
                    "other": "MCP 工具调用",
                }
                res_clean = _clean_mcp_result(item.get("result"))
                err = item.get("error")
                rec = steps_by_id.get(iid)
                if rec is None:
                    rec = {
                        "step_no": len(ordered_steps) + 1,
                        "item_id": iid,
                        "kind": chan,
                        "kind_zh": kind_zh_map.get(chan, "MCP 工具调用"),
                        "server": server,
                        "tool": tool,
                        "tool_zh": translate_tool_name(tool),
                        "title": f"{translate_tool_name(tool)} · {full_tool}",
                        "arguments": item.get("arguments"),
                        "result_text": res_clean["text"],
                        "base64_omitted": res_clean["base64_omitted"],
                        "error": err,
                        "status": item.get("status", "completed"),
                    }
                    steps_by_id[iid] = rec
                    ordered_steps.append(rec)
                    counts[chan] = counts.get(chan, 0) + 1
                else:
                    rec["status"] = item.get("status", rec["status"])
                    if res_clean["text"]:
                        rec["result_text"] = res_clean["text"]
                    if res_clean["base64_omitted"]:
                        rec["base64_omitted"] = res_clean["base64_omitted"]
                    if err is not None:
                        rec["error"] = err

            elif itype == "command_execution":
                rec = steps_by_id.get(iid)
                if rec is None:
                    rec = {
                        "step_no": len(ordered_steps) + 1,
                        "item_id": iid,
                        "kind": "cli",
                        "kind_zh": "容器本地命令",
                        "server": "local_shell",
                        "tool": "command_execution",
                        "tool_zh": "容器 Shell 命令",
                        "title": "本地 Shell 执行",
                        "arguments": {"command": item.get("command", "")},
                        "result_text": item.get("aggregated_output", ""),
                        "base64_omitted": [],
                        "exit_code": item.get("exit_code"),
                        "status": item.get("status", "completed"),
                    }
                    steps_by_id[iid] = rec
                    ordered_steps.append(rec)
                    counts["cli"] += 1
                else:
                    rec["status"] = item.get("status", rec["status"])
                    if item.get("aggregated_output"):
                        rec["result_text"] = item["aggregated_output"]
                    if item.get("exit_code") is not None:
                        rec["exit_code"] = item["exit_code"]

    # 按顺序将 actions.jsonl 的时间戳与窗口焦点信息补充关联到 MCP 调用步骤
    mcp_steps = [s for s in ordered_steps if s.get("server") not in (None, "local_shell")]
    if actions_rows:
        t0 = float(actions_rows[0].get("start_wall") or actions_rows[0].get("timestamp") or 0.0)
        for s, a in zip(mcp_steps, actions_rows):
            ts = float(a.get("start_wall") or a.get("timestamp") or t0)
            s["rel_s"] = round(max(0.0, ts - t0), 2)
            if a.get("duration_s") is not None:
                s["duration_s"] = round(float(a["duration_s"]), 3)
            if a.get("win_before") or a.get("win_after"):
                s["win_before"] = a.get("win_before", "")
                s["win_after"] = a.get("win_after", "")

    usage_summary = {
        "turns": len(turn_usages),
        "input_tokens": sum(int(u.get("input_tokens") or 0) for u in turn_usages) or actor_meta.get("input_tokens"),
        "cached_input_tokens": sum(int(u.get("cached_input_tokens") or 0) for u in turn_usages) or actor_meta.get("cached_input_tokens"),
        "output_tokens": sum(int(u.get("output_tokens") or 0) for u in turn_usages) or actor_meta.get("output_tokens"),
        "reasoning_output_tokens": sum(int(u.get("reasoning_output_tokens") or 0) for u in turn_usages) or actor_meta.get("reasoning_output_tokens"),
    }

    return {
        "case_id": case_id,
        "ep_name": ep_name,
        "role": role,
        "name_zh": actor_meta["name_zh"],
        "brief_zh": actor_meta["brief_zh"],
        "actor_meta": actor_meta,
        "usage": usage_summary,
        "counts": counts,
        "total_steps": len(ordered_steps),
        "actions_count": len(actions_rows),
        "steps": ordered_steps,
    }
