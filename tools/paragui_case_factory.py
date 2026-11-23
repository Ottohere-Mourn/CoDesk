#!/usr/bin/env python3
"""ParaGUI Case Manufacturing, Upstream Pairing & Horizon-Calibration Toolkit.

Distills the empirical conflict laws and natural task-length distributions observed
in Qwen/RecreationBench (RB-B1..B7, 14 apps, 50 Ubuntu tasks) and OSWorld-V2
(OSW2-P1..P15, 30 official tasks under Qwen-CUA 0.27.0 + full CLI):

1. Six Empirical GUI+CLI Conflict Laws (LAW_1 .. LAW_6):
   - LAW_1_KEYSTROKE_MISROUTING: Semantic AT-SPI click ('app=' isolation illusion)
     paired with X11 global keyboard focus routing (48.6%–61.5% misrouting in RB-B4/B6).
   - LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP: Same-title sub-dialogs ('Preferences',
     'Open', 'Configure') and modal file choosers hijacking peer turns (RB-B2/B3/B5).
   - LAW_3_AUTOHIDE_POPOVER_AND_CANDIDATE_LAUNCH: Focus-loss autohiding CSD/F10 popovers
     plus 'explore -> implement -> launch candidate window on :99 -> verify' loops (RB-B4/B5).
   - LAW_4_SINGLETON_CDP_VIEWPORT_VS_FULLSCREEN_CAPTURE: Shared :9222 browser where
     multi-breakpoint/modal interactive QA collides with F11 1920x1080 walkthrough capture
     (OSW2-P5: Role A 0.939 -> 0.000, 635s overlap).
   - LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB: Multi-dock / '_NET_WM_STATE_ABOVE'
     stacking intercepting coordinate drag strokes on opaque 2D/OpenGL canvases while
     polluting root-window screen captures (RB-B5 Pencil2D+ksnip, RB-B7 SolveSpace+Bruno).
   - LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN: Single-window MDI sibling tabs
     (OSW2-P3 WPS), single soffice.bin (Calc+Writer), or locked SQLite/BibTeX workbenches
     (OSW2-P8/P9) with live dirty buffers vs CLI updates.

2. Natural Horizon, Role Symmetry & Non-Saturated Rubric Calibration:
   - Target isolated role duration: 360s–960s (6–16 minutes), matching RB (322s–1002s)
     and OSWorld-V2 (611s–1390s) rather than 90s micro-tasks.
   - Role duration symmetry ratio: min(T_a, T_b) / max(T_a, T_b) >= 0.65 so predicted
     concurrent GUI overlap exceeds 300s (overlap_ratio >= 0.60).
   - Fine-grained continuous rubric: >= 20 partial-credit subchecks per case across
     programmatic, AT-SPI/DOM structural, and visual assertions so isolated baselines
     land in the informative 0.40–0.92 band without ceiling saturation.
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
from pathlib import Path
import sys
from typing import Any

CONFLICT_LAWS: dict[str, dict[str, Any]] = {
    "LAW_1_KEYSTROKE_MISROUTING": {
        "title": "AT-SPI Semantic Click Illusion vs. Global X11 Keyboard Focus Misrouting",
        "empirical_anchor": "RB-B6 wxFormBuilder+wxMEdit (61.5% misrouted hotkeys, +234% tokens); RB-B4 Spedread+Breathing",
        "required_surfaces": ("atspi_click_plus_global_hotkeys", "iterative_keyboard_shortcuts"),
        "weight": 22.0,
    },
    "LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP": {
        "title": "Same-Title Sub-Dialogs ('Preferences'/'Open') & Modal File-Chooser Hijack",
        "empirical_anchor": "RB-B2 FSearch+Xarchiver (-10.5% on Xarchiver); RB-B3 DB Browser+KSudoku (-42.3% on KSudoku)",
        "required_surfaces": ("twin_named_modals", "modal_file_or_rule_dialog"),
        "weight": 20.0,
    },
    "LAW_3_AUTOHIDE_POPOVER_AND_CANDIDATE_LAUNCH": {
        "title": "Focus-Loss Autohiding CSD/F10 Popovers & Live Candidate Window Verification on :99",
        "empirical_anchor": "RB-B4 GTK4 GtkPopoverMenu (menu=0/5); RB-B1..B7 candidate window launch onto shared :99",
        "required_surfaces": ("autohide_popover_or_ephemeral_menu", "candidate_window_launch_on_shared_display"),
        "weight": 18.0,
    },
    "LAW_4_SINGLETON_CDP_VIEWPORT_VS_FULLSCREEN_CAPTURE": {
        "title": "Singleton :9222 CDP Multi-Viewport Interactive QA vs. Unobstructed 1920x1080 Walkthrough",
        "empirical_anchor": "OSW2-P5 Chrome :8080 58-item QA + :4000 7-scene GIF (Role A 0.939 -> 0.000, 635s overlap)",
        "required_surfaces": ("singleton_cdp_browser", "viewport_resize_vs_fullscreen_capture"),
        "weight": 24.0,
    },
    "LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB": {
        "title": "Floating Tool Docks & Always-on-Top Z-Order War vs. Opaque 2D Canvas Drag & Root Grab",
        "empirical_anchor": "RB-B5 7-dock Pencil2D + ksnip (+92% tokens); RB-B7 SolveSpace OpenGL drag vs Bruno wmctrl above",
        "required_surfaces": ("custom_2d_canvas_drag", "overlapping_docks_or_root_screencap"),
        "weight": 20.0,
    },
    "LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN": {
        "title": "Single-Window MDI Sibling Tabs, Single soffice.bin & Locked SQLite/BibTeX Split-Brain",
        "empirical_anchor": "OSW2-P3 WPS MDI tabs (1.0 -> 0.0); OSW2-P8/P9 Zotero sqlite + BibTeX; EC2-C06 soffice.bin",
        "required_surfaces": ("single_instance_mdi_or_soffice", "shared_db_or_dirty_gui_buffer"),
        "weight": 18.0,
    },
}

HORIZON_BANDS: dict[str, dict[str, Any]] = {
    "compact_live_qa": {
        "target_iso_role_s": (300, 600),
        "rec_conc_timeout_s": 1200,
        "min_subchecks_total": 24,
        "description": "High-density live CDP/GUI verification & walkthrough capture (5–10m natural horizon).",
    },
    "recreation_explore_build_verify": {
        "target_iso_role_s": (420, 900),
        "rec_conc_timeout_s": 1680,
        "min_subchecks_total": 28,
        "description": "Zero-source reference GUI exploration -> standalone GUI app implementation -> :99 candidate verify (7–15m).",
    },
    "deep_coupled_workbench": {
        "target_iso_role_s": (420, 960),
        "rec_conc_timeout_s": 1800,
        "min_subchecks_total": 24,
        "description": "Multi-stage corpus/MDI/CAD/portal engineering with coupled invariants (7–16m).",
    },
}


def infer_rb_app_traits(entry: dict[str, Any]) -> dict[str, Any]:
    """Estimate natural horizon and GUI conflict traits for one RecreationBench Ubuntu entry."""
    diff = str(entry.get("difficulty") or "medium").lower()
    prog = int(entry.get("prog_total") or entry.get("programmatic_test_count") or 40)
    vlm = int(entry.get("vlm_total") or entry.get("vlm_assertion_count") or 20)
    text = json.dumps(entry, ensure_ascii=False).lower()

    base_s = {"easy": 310.0, "medium": 520.0, "hard": 780.0}.get(diff, 480.0)
    est_s = round(base_s + 2.8 * prog + 1.6 * vlm, 1)
    est_cua = min(60, max(28, int(round(24 + 0.35 * prog + 0.15 * vlm))))
    est_cli = min(38, max(8, int(round(7 + 0.20 * prog + (8 if diff == "hard" else 3)))))

    traits: set[str] = {"candidate_window_launch_on_shared_display", "exploration_as_oracle"}
    if any(k in text for k in ("gtk-4", "gtk4", "libadwaita", "adw", "popover", "csd", "spedread", "breathing", "smile")):
        traits.update({"autohide_popover_or_ephemeral_menu", "atspi_click_plus_global_hotkeys"})
    if any(k in text for k in ("wx", "wxwidgets", "hex", "editor", "notepad", "medit", "code", "shortcut")):
        traits.update({"iterative_keyboard_shortcuts", "atspi_click_plus_global_hotkeys"})
    if any(k in text for k in ("sqlite", "archive", "xarchiver", "fsearch", "qdirstat", "cherrytree", "pwsafe", "krename")):
        traits.update({"twin_named_modals", "modal_file_or_rule_dialog"})
    if any(k in text for k in ("pencil", "canvas", "solvespace", "cad", "camunda", "draw", "paint", "diagram")):
        traits.add("custom_2d_canvas_drag")
    if any(k in text for k in ("ksnip", "screenshot", "capture", "pomatez", "bruno", "electron")):
        traits.add("overlapping_docks_or_root_screencap")

    return {
        "instance_id": entry.get("instance_id") or entry.get("id") or entry.get("slug"),
        "slug": entry.get("slug") or str(entry.get("instance_id", "")).split("/")[-1],
        "difficulty": diff,
        "prog_total": prog,
        "vlm_total": vlm,
        "est_role_seconds": est_s,
        "est_cua_calls": est_cua,
        "est_cli_calls": est_cli,
        "traits": sorted(traits),
    }


def score_role_pair(role_a: dict[str, Any], role_b: dict[str, Any]) -> dict[str, Any]:
    """Score a two-role desktop pairing on horizon symmetry, overlap duration, and Laws 1..6."""
    ta = float(role_a["est_role_seconds"])
    tb = float(role_b["est_role_seconds"])
    hi = max(ta, tb, 1.0)
    lo = min(ta, tb)
    symmetry = round(lo / hi, 3)
    # Empirical RB/OSW2 overlap factor (~0.78 of min role duration when barrier-synchronized)
    est_overlap_s = round(0.78 * lo, 1)

    tr_a = set(role_a.get("traits") or ())
    tr_b = set(role_b.get("traits") or ())
    union_tr = tr_a | tr_b

    active_laws: list[str] = []
    law_points = 0.0
    if "atspi_click_plus_global_hotkeys" in union_tr and ("iterative_keyboard_shortcuts" in union_tr or len(tr_a & tr_b) >= 2):
        active_laws.append("LAW_1_KEYSTROKE_MISROUTING")
        law_points += 22.0
    if ("twin_named_modals" in tr_a and "twin_named_modals" in tr_b) or "modal_file_or_rule_dialog" in union_tr:
        active_laws.append("LAW_2_TWIN_MODAL_AND_FILE_CHOOSER_TRAP")
        law_points += 20.0 if ("twin_named_modals" in tr_a and "twin_named_modals" in tr_b) else 13.0
    if "autohide_popover_or_ephemeral_menu" in union_tr and "candidate_window_launch_on_shared_display" in union_tr:
        active_laws.append("LAW_3_AUTOHIDE_POPOVER_AND_CANDIDATE_LAUNCH")
        law_points += 18.0
    if "singleton_cdp_browser" in tr_a and "singleton_cdp_browser" in tr_b:
        active_laws.append("LAW_4_SINGLETON_CDP_VIEWPORT_VS_FULLSCREEN_CAPTURE")
        law_points += 24.0
    if "custom_2d_canvas_drag" in union_tr and ("overlapping_docks_or_root_screencap" in union_tr or "custom_2d_canvas_drag" in (tr_a & tr_b)):
        active_laws.append("LAW_5_ZORDER_DOCKS_VS_CANVAS_DRAG_AND_SCREEN_GRAB")
        law_points += 20.0
    if "single_instance_mdi_or_soffice" in union_tr or "shared_db_or_dirty_gui_buffer" in union_tr:
        active_laws.append("LAW_6_SINGLE_INSTANCE_MDI_AND_PROFILE_SPLIT_BRAIN")
        law_points += 18.0

    horizon_bonus = 18.0 if (300.0 <= lo <= 960.0 and symmetry >= 0.65) else (8.0 if lo >= 240.0 else 0.0)
    overlap_bonus = min(16.0, round(est_overlap_s / 30.0, 2))
    sym_bonus = round(6.0 * symmetry, 2)
    total_idx = round(min(100.0, law_points + horizon_bonus + overlap_bonus + sym_bonus), 2)
    rec_timeout = int(round(max(1200.0, hi * 1.95) / 60.0) * 60)

    return {
        "role_a": role_a["slug"],
        "role_b": role_b["slug"],
        "est_role_a_s": ta,
        "est_role_b_s": tb,
        "horizon_symmetry_ratio": symmetry,
        "est_overlap_seconds": est_overlap_s,
        "recommended_conc_timeout_s": rec_timeout,
        "active_conflict_laws": active_laws,
        "predicted_contention_index": total_idx,
    }


def audit_case_blueprint_meta(meta: dict[str, Any], mod: Any | None = None) -> dict[str, Any]:
    """Evaluate a synthesized ParaGUI case module against RB + OSW2 horizon & conflict-law standards."""
    bp = meta.get("factory_blueprint") or {}
    ra_spec = bp.get("role_a") or {
        "slug": meta["roles"][0],
        "est_role_seconds": float(bp.get("est_role_a_s", 450.0)),
        "traits": list(bp.get("traits_a") or meta.get("archetypes") or ()),
    }
    rb_spec = bp.get("role_b") or {
        "slug": meta["roles"][1],
        "est_role_seconds": float(bp.get("est_role_b_s", 450.0)),
        "traits": list(bp.get("traits_b") or meta.get("archetypes") or ()),
    }
    pair_score = score_role_pair(ra_spec, rb_spec)
    subcheck_count = int(bp.get("total_subchecks", 0))
    cli_bypass_resistance = float(bp.get("cli_bypass_resistance", 0.90))
    horizon_band = str(bp.get("horizon_band", "recreation_explore_build_verify"))
    band_cfg = HORIZON_BANDS.get(horizon_band, HORIZON_BANDS["compact_live_qa"])

    warnings: list[str] = []
    if pair_score["horizon_symmetry_ratio"] < 0.65:
        warnings.append(f"Role duration asymmetry ({pair_score['horizon_symmetry_ratio']} < 0.65) risks early single-role exit")
    if pair_score["est_overlap_seconds"] < 240.0:
        warnings.append(f"Predicted overlap ({pair_score['est_overlap_seconds']}s < 240s) shorter than RB/OSW2 contention regime")
    if subcheck_count < int(band_cfg["min_subchecks_total"]):
        warnings.append(f"Rubric subchecks ({subcheck_count}) below {band_cfg['min_subchecks_total']} partial-credit granularity target")
    if cli_bypass_resistance < 0.80:
        warnings.append(f"CLI-bypass resistance ({cli_bypass_resistance}) < 0.80; ground oracle in live GUI/CDP/framebuffer")
    if float(meta.get("conc_role_timeout_s", 0)) < 1.75 * max(pair_score["est_role_a_s"], pair_score["est_role_b_s"]):
        warnings.append("conc_role_timeout_s provides < 1.75x recovery slack over isolated role horizon")

    prompt_ok = True
    if mod is not None and hasattr(mod, "build_tickets_by_role"):
        tickets = mod.build_tickets_by_role()
        joined = "\n".join(tickets.values()).lower()
        prompt_ok = not any(bad in joined for bad in ("other agent", "peer agent", "do not modify", "ctrl+z"))
        if not prompt_ok:
            warnings.append("Prompt hygiene violation in build_tickets_by_role()")

    return {
        "task_id": meta["id"],
        "title": meta["title"],
        "track": meta["track"],
        "workspace_mode": meta["workspace_mode"],
        "horizon_band": horizon_band,
        "total_subchecks": subcheck_count,
        "cli_bypass_resistance": cli_bypass_resistance,
        **pair_score,
        "prompt_hygiene_ok": prompt_ok,
        "blueprint_valid": len(warnings) == 0,
        "warnings": warnings,
    }


def cmd_laws(_args: argparse.Namespace) -> int:
    print(json.dumps({"conflict_laws": CONFLICT_LAWS, "horizon_bands": HORIZON_BANDS}, indent=2, ensure_ascii=False))
    return 0


def cmd_mine_upstream(args: argparse.Namespace) -> int:
    rb_path = args.rb_jsonl.resolve()
    entries: list[dict[str, Any]] = []
    for ln in rb_path.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            entries.append(infer_rb_app_traits(json.loads(ln)))

    scored_pairs: list[dict[str, Any]] = []
    for a, b in itertools.combinations(entries, 2):
        ps = score_role_pair(a, b)
        if ps["horizon_symmetry_ratio"] >= args.min_symmetry and len(ps["active_conflict_laws"]) >= 1:
            scored_pairs.append(ps)
    scored_pairs.sort(
        key=lambda r: (r["predicted_contention_index"], r["horizon_symmetry_ratio"], r["est_overlap_seconds"]),
        reverse=True,
    )
    top = scored_pairs[: args.top_k]
    out_obj = {
        "source": str(rb_path),
        "total_apps": len(entries),
        "eligible_pairs": len(scored_pairs),
        "top_pairs": top,
    }
    if args.out:
        args.out.write_text(json.dumps(out_obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out_obj, indent=2, ensure_ascii=False))
    return 0


def cmd_audit_suite(args: argparse.Namespace) -> int:
    target = args.target.resolve()
    py_files = sorted(p for p in target.glob("*.py") if p.name not in {"__init__.py", "common.py", "registry.py"}) if target.is_dir() else [target]
    reports: list[dict[str, Any]] = []
    for pf in py_files:
        spec = importlib.util.spec_from_file_location(pf.stem, pf)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "META"):
            reports.append(audit_case_blueprint_meta(mod.META, mod))
    summary = {
        "audited_cases": len(reports),
        "all_blueprints_valid": all(r["blueprint_valid"] for r in reports),
        "mean_predicted_contention_index": round(sum(r["predicted_contention_index"] for r in reports) / max(1, len(reports)), 2),
        "mean_est_overlap_seconds": round(sum(r["est_overlap_seconds"] for r in reports) / max(1, len(reports)), 1),
        "cases": reports,
    }
    if args.out:
        args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["all_blueprints_valid"] else 1


SCAFFOLD_TEMPLATE = '''"""__CASE_ID__: __TITLE__ (Synthesized via tools/paragui_case_factory.py)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

TASK_ID = "__CASE_ID__"
PORTAL_PORT = __PORT__

META: dict[str, Any] = {
    "id": TASK_ID,
    "title": "__TITLE__",
    "domain": "__DOMAIN__",
    "track": "__TRACK__",
    "workspace_mode": "__WS_MODE__",
    "archetypes": (__LAWS_TUPLE__),
    "roles": ("__ROLE_A__", "__ROLE_B__"),
    "portal_port": PORTAL_PORT,
    "extra_ports": (),
    "open_gui_docs": (),
    "conc_role_timeout_s": __TIMEOUT_S__,
    "iso_role_timeout_s": __TIMEOUT_S__,
    "max_cua_calls": 60,
    "factory_blueprint": {
        "horizon_band": "__BAND__",
        "total_subchecks": 26,
        "cli_bypass_resistance": 0.92,
        "role_a": {"slug": "__ROLE_A__", "est_role_seconds": __EST_S__, "traits": [__TRAITS_LIST__]},
        "role_b": {"slug": "__ROLE_B__", "est_role_seconds": __EST_S__, "traits": [__TRAITS_LIST__]},
    },
}
'''


def cmd_scaffold(args: argparse.Namespace) -> int:
    band = HORIZON_BANDS[args.horizon_band]
    est_s = 0.5 * (band["target_iso_role_s"][0] + band["target_iso_role_s"][1])
    ws_mode = "isolated" if args.track == "track1_isolated_screen" else "shared"
    laws_str = ", ".join(json.dumps(x) for x in args.laws) + ("," if len(args.laws) == 1 else "")
    traits: list[str] = []
    for lw in args.laws:
        traits.extend(CONFLICT_LAWS[lw]["required_surfaces"])
    traits_str = ", ".join(json.dumps(t) for t in sorted(set(traits)))
    rendered = (
        SCAFFOLD_TEMPLATE.replace("__CASE_ID__", args.case_id)
        .replace("__TITLE__", args.title)
        .replace("__DOMAIN__", args.domain)
        .replace("__TRACK__", args.track)
        .replace("__WS_MODE__", ws_mode)
        .replace("__LAWS_TUPLE__", laws_str)
        .replace("__ROLE_A__", args.role_a)
        .replace("__ROLE_B__", args.role_b)
        .replace("__PORT__", str(args.port))
        .replace("__TIMEOUT_S__", str(band["rec_conc_timeout_s"]))
        .replace("__BAND__", args.horizon_band)
        .replace("__EST_S__", str(round(est_s, 1)))
        .replace("__TRAITS_LIST__", traits_str)
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8")
    print(f"WROTE_SCAFFOLD: {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("laws", help="Print the 6 RB/OSW2 conflict laws and horizon calibration bands.")

    p_m = sub.add_parser("mine-upstream", help="Rank high-overlap, high-conflict pairs from RecreationBench metadata.")
    p_m.add_argument("--rb-jsonl", type=Path, required=True)
    p_m.add_argument("--min-symmetry", type=float, default=0.68)
    p_m.add_argument("--top-k", type=int, default=12)
    p_m.add_argument("--out", type=Path, default=None)

    p_a = sub.add_parser("audit-suite", help="Score case modules on horizon symmetry, overlap, rubric granularity & Laws 1..6.")
    p_a.add_argument("target", type=Path)
    p_a.add_argument("--out", type=Path, default=None)

    p_s = sub.add_parser("scaffold", help="Generate a horizon-calibrated case skeleton grounded in Laws 1..6.")
    p_s.add_argument("--case-id", required=True)
    p_s.add_argument("--title", required=True)
    p_s.add_argument("--domain", default="Desktop Engineering & Live Verification")
    p_s.add_argument("--track", choices=("track1_isolated_screen", "track2_shared_state"), default="track1_isolated_screen")
    p_s.add_argument("--horizon-band", choices=tuple(HORIZON_BANDS.keys()), default="recreation_explore_build_verify")
    p_s.add_argument("--laws", nargs="+", choices=tuple(CONFLICT_LAWS.keys()), required=True)
    p_s.add_argument("--role-a", default="role_alpha")
    p_s.add_argument("--role-b", default="role_beta")
    p_s.add_argument("--port", type=int, default=19301)
    p_s.add_argument("--out", type=Path, required=True)

    args = ap.parse_args(argv)
    if args.cmd == "laws":
        return cmd_laws(args)
    if args.cmd == "mine-upstream":
        return cmd_mine_upstream(args)
    if args.cmd == "audit-suite":
        return cmd_audit_suite(args)
    if args.cmd == "scaffold":
        return cmd_scaffold(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
