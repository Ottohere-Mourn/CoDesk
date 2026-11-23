"""Multi-driver (qwen-cua-driver 0.27.0 / xdotool) GUI+CLI runner & 5-gate validator for rb_osw2_synth_v1."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import threading
import time
from typing import Any

from experiments.deepseek_v41_eval import analyze_race_awareness
from experiments.exam_contention_v2 import (
    ExamV2Desktop,
    RoleMcpBridge,
    _run_desk_reg,
    build_ec2_agent_prompt,
    run_ec2_actor,
    summarize_ec2_telemetry,
)
from tasks.rb_osw2_synth_v1.common import read_json_safe, write_json
from tasks.rb_osw2_synth_v1.registry import RBS_BY_ID, RBS_CATALOG

RBS_REGISTRY_MOD = "tasks.rb_osw2_synth_v1.registry"
RBS_EXTRA_PKGS = ("tasks/rb_osw2_synth_v1",)


def _make_rbs_desktop(cond_dir: Path, task_id: str, code_root: Path, active_roles: tuple[str, ...] | None = None) -> ExamV2Desktop:
    return ExamV2Desktop(
        cond_dir=cond_dir,
        task_id=task_id,
        code_root=code_root,
        active_roles=active_roles,
        record_video=False,
        registry_module=RBS_REGISTRY_MOD,
        meta_map=RBS_BY_ID,
        extra_task_packages=RBS_EXTRA_PKGS,
    )


def self_validate_rbs_case(task_id: str, out_dir: Path, code_root: Path) -> dict[str, Any]:
    meta = RBS_BY_ID[task_id]
    ra, rb = meta["roles"]
    cdir = out_dir / task_id
    cdir.mkdir(parents=True, exist_ok=True)

    d1 = _make_rbs_desktop(cdir / "gate1_pristine", task_id, code_root)
    d1.build_pristine()
    try:
        d1.start()
    finally:
        g1 = d1.stop_and_grade()

    d2 = _make_rbs_desktop(cdir / "gate2_seq_ab", task_id, code_root)
    d2.build_pristine()
    try:
        d2.start()
        _run_desk_reg(d2, ["solve_role", "--task", task_id, "--role", ra, "--workspace-root", "/ws_root"])
        _run_desk_reg(d2, ["solve_role", "--task", task_id, "--role", rb, "--workspace-root", "/ws_root"])
    finally:
        g2 = d2.stop_and_grade()

    d3 = _make_rbs_desktop(cdir / "gate3_seq_ba", task_id, code_root)
    d3.build_pristine()
    try:
        d3.start()
        _run_desk_reg(d3, ["solve_role", "--task", task_id, "--role", rb, "--workspace-root", "/ws_root"])
        _run_desk_reg(d3, ["solve_role", "--task", task_id, "--role", ra, "--workspace-root", "/ws_root"])
    finally:
        g3 = d3.stop_and_grade()

    d4 = _make_rbs_desktop(cdir / "gate4_contention", task_id, code_root)
    d4.build_pristine()
    try:
        d4.start()
        _run_desk_reg(d4, ["sim_contention", "--task", task_id, "--workspace-root", "/ws_root", "--state-dir", "/opt/ec2_state"])
    finally:
        g4 = d4.stop_and_grade()

    d5 = _make_rbs_desktop(cdir / "gate5_careful_conc", task_id, code_root)
    d5.build_pristine()
    t5_0 = time.monotonic()
    t5_s = 9999.0
    try:
        d5.start()
        t5_0 = time.monotonic()
        _run_desk_reg(d5, ["careful_conc", "--task", task_id, "--workspace-root", "/ws_root"])
        t5_s = round(time.monotonic() - t5_0, 2)
    finally:
        g5 = d5.stop_and_grade(wall_override_s=round(time.monotonic() - t5_0, 2))

    conc_budget = float(meta["conc_role_timeout_s"])
    gate4_active = (g4["joint_pass"] is False) or (g4["mean_score"] < 0.96)
    all_ok = (
        g1["joint_pass"] is False
        and g1["mean_score"] <= 0.20
        and g2["joint_pass"] is True
        and g2["mean_score"] >= 0.99
        and g3["joint_pass"] is True
        and g3["mean_score"] >= 0.99
        and gate4_active
        and g5["joint_pass"] is True
        and g5["mean_score"] >= 0.99
        and t5_s <= 0.55 * conc_budget
        and bool(g2["prompt_hygiene"]["ok"])
    )
    out = {
        "task_id": task_id,
        "title": meta["title"],
        "domain": meta["domain"],
        "track": meta["track"],
        "workspace_mode": meta["workspace_mode"],
        "roles": [ra, rb],
        "gate1_pristine_pass": g1["joint_pass"],
        "gate1_pristine_score": g1["mean_score"],
        "gate2_seq_ab_pass": g2["joint_pass"],
        "gate2_seq_ab_score": g2["mean_score"],
        "gate3_seq_ba_pass": g3["joint_pass"],
        "gate3_seq_ba_score": g3["mean_score"],
        "gate4_contention_pass": g4["joint_pass"],
        "gate4_contention_score": g4["mean_score"],
        "gate4_contention_surface_active": gate4_active,
        "gate5_careful_conc_pass": g5["joint_pass"],
        "gate5_careful_conc_score": g5["mean_score"],
        "gate5_careful_conc_seconds": t5_s,
        "conc_role_timeout_s": conc_budget,
        "gate5_within_55pct_budget": t5_s <= 0.55 * conc_budget,
        "prompt_hygiene": g2["prompt_hygiene"],
        "all_5_gates_valid": all_ok,
        "diagnostics": {
            "seq_ab_errors": g2["errors_a"] + g2["errors_b"] + g2["errors_joint"],
            "seq_ba_errors": g3["errors_a"] + g3["errors_b"] + g3["errors_joint"],
            "contention_errors": g4["errors_a"] + g4["errors_b"] + g4["errors_joint"],
            "careful_conc_errors": g5["errors_a"] + g5["errors_b"] + g5["errors_joint"],
        },
    }
    write_json(cdir / "self_validation_5gate.json", out)
    return out


def run_rbs_case(
    task_id: str,
    mode: str,
    out_dir: Path,
    code_root: Path,
    api_cfg: dict[str, Any],
    codex_bin: Path,
    gui_driver: str = "qwen_cua",
) -> dict[str, Any]:
    meta = RBS_BY_ID[task_id]
    ra, rb = meta["roles"]
    m_slug = str(api_cfg.get("model", "model")).replace(".", "_")
    cond_dir = out_dir / task_id / f"{mode}_{m_slug}"
    cond_dir.mkdir(parents=True, exist_ok=True)
    max_cua = int(meta.get("max_cua_calls", 65))

    existing_grade = cond_dir / "grade.json"
    existing_actors = {r: cond_dir / f"actor_{r}" / "actor_summary.json" for r in (ra, rb)}
    if existing_grade.is_file() and all(p.is_file() for p in existing_actors.values()):
        grade_res = read_json_safe(existing_grade)
        actors = {r: read_json_safe(existing_actors[r]) for r in (ra, rb)}
        if mode == "isolated":
            wall_s = round(max(float(actors[ra]["wall_seconds"]), float(actors[rb]["wall_seconds"])), 2)
            per_r_tel = {}
            for r in (ra, rb):
                al = cond_dir / f"actor_{r}" / "actions.jsonl"
                evs = [json.loads(ln) for ln in al.read_text(encoding="utf-8").splitlines() if ln.strip()] if al.is_file() else []
                per_r_tel[r] = summarize_ec2_telemetry(evs, (ra, rb), None, None)
            contention_tel = {
                "total_events": per_r_tel[ra]["total_events"] + per_r_tel[rb]["total_events"],
                "interleaving_role_switches": 0,
                "overlap_seconds": 0.0,
                "focus_flips": per_r_tel[ra]["focus_flips"] + per_r_tel[rb]["focus_flips"],
                "misrouted_keystrokes": 0,
                "pointer_moves": per_r_tel[ra]["pointer_moves"] + per_r_tel[rb]["pointer_moves"],
                "clipboard_changes": per_r_tel[ra]["clipboard_changes"] + per_r_tel[rb]["clipboard_changes"],
            }
        else:
            wall_s = round(max(float(actors[ra]["wall_seconds"]), float(actors[rb]["wall_seconds"])), 2)
            stl_p = cond_dir / "shared_timeline.json"
            shared_tl = json.loads(stl_p.read_text(encoding="utf-8")) if stl_p.is_file() else []
            contention_tel = summarize_ec2_telemetry(shared_tl, (ra, rb), None, None)
    elif mode == "isolated":
        lim = int(meta["iso_role_timeout_s"])
        t0 = time.monotonic()

        def _run_iso(role: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
            sub_d = cond_dir / f"iso_{role}"
            desk_r = _make_rbs_desktop(sub_d, task_id, code_root, active_roles=(role,))
            desk_r.build_pristine()
            t_md = (desk_r.tickets_root / role / "task.md").read_text(encoding="utf-8")
            desk_r.start()
            tl_r: list[dict[str, Any]] = []
            lk_r = threading.Lock()
            rt0 = time.monotonic()
            try:
                act_s, br_r = run_ec2_actor(
                    desk=desk_r,
                    role=role,
                    actor_dir=cond_dir / f"actor_{role}",
                    prompt_text=build_ec2_agent_prompt(t_md, role, lim, gui_driver, max_cua),
                    api_cfg=api_cfg,
                    codex_bin=codex_bin,
                    timeout_s=lim,
                    gui_driver=gui_driver,
                    max_cua_calls=max_cua,
                    shared_timeline=tl_r,
                    timeline_lock=lk_r,
                    barrier=None,
                )
            finally:
                gr_r = desk_r.stop_and_grade(wall_override_s=round(time.monotonic() - rt0, 2))
            tel_r = summarize_ec2_telemetry(tl_r, (ra, rb), br_r if role == ra else None, br_r if role == rb else None)
            return act_s, gr_r, tel_r

        with ThreadPoolExecutor(max_workers=2) as pool:
            fa = pool.submit(_run_iso, ra)
            fb = pool.submit(_run_iso, rb)
            act_a, gr_a, tel_a = fa.result()
            act_b, gr_b, tel_b = fb.result()

        wall_s = round(time.monotonic() - t0, 2)
        grade_res = {
            "task_id": task_id,
            "score_a": gr_a["score_a"],
            "score_b": gr_b["score_b"],
            "mean_score": round(0.5 * (gr_a["score_a"] + gr_b["score_b"]), 4),
            "pass_a": gr_a["pass_a"],
            "pass_b": gr_b["pass_b"],
            "joint_pass": bool(gr_a["pass_a"] and gr_b["pass_b"]),
            "subchecks_a": gr_a["subchecks_a"],
            "subchecks_b": gr_b["subchecks_b"],
            "errors_a": gr_a["errors_a"],
            "errors_b": gr_b["errors_b"],
            "errors_joint": [],
            "prompt_hygiene": gr_a["prompt_hygiene"],
            "telemetry_a": gr_a.get("telemetry"),
            "telemetry_b": gr_b.get("telemetry"),
        }
        actors = {ra: act_a, rb: act_b}
        contention_tel = {
            "total_events": tel_a["total_events"] + tel_b["total_events"],
            "interleaving_role_switches": 0,
            "overlap_seconds": 0.0,
            "focus_flips": tel_a["focus_flips"] + tel_b["focus_flips"],
            "misrouted_keystrokes": 0,
            "pointer_moves": tel_a["pointer_moves"] + tel_b["pointer_moves"],
            "clipboard_changes": tel_a["clipboard_changes"] + tel_b["clipboard_changes"],
        }
        write_json(cond_dir / "grade.json", grade_res)
    else:
        desk = _make_rbs_desktop(cond_dir, task_id, code_root, active_roles=(ra, rb))
        desk.build_pristine()
        tickets = {r: (desk.tickets_root / r / "task.md").read_text(encoding="utf-8") for r in (ra, rb)}
        desk.start()
        shared_tl: list[dict[str, Any]] = []
        tl_lock = threading.Lock()
        actors = {}
        bridges: dict[str, RoleMcpBridge] = {}
        t0 = time.monotonic()
        try:
            lim = int(meta["conc_role_timeout_s"])
            bar = threading.Barrier(2) if mode == "shared" else None
            if mode == "shared":
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futs = {
                        pool.submit(
                            run_ec2_actor,
                            desk=desk,
                            role=r,
                            actor_dir=cond_dir / f"actor_{r}",
                            prompt_text=build_ec2_agent_prompt(tickets[r], r, lim, gui_driver, max_cua),
                            api_cfg=api_cfg,
                            codex_bin=codex_bin,
                            timeout_s=lim,
                            gui_driver=gui_driver,
                            max_cua_calls=max_cua,
                            shared_timeline=shared_tl,
                            timeline_lock=tl_lock,
                            barrier=bar,
                        ): r
                        for r in (ra, rb)
                    }
                    for f in as_completed(futs):
                        rk = futs[f]
                        actors[rk], bridges[rk] = f.result()
            else:
                order = (ra, rb) if mode == "seq_ab" else (rb, ra)
                for rk in order:
                    actors[rk], bridges[rk] = run_ec2_actor(
                        desk=desk,
                        role=rk,
                        actor_dir=cond_dir / f"actor_{rk}",
                        prompt_text=build_ec2_agent_prompt(tickets[rk], rk, lim, gui_driver, max_cua),
                        api_cfg=api_cfg,
                        codex_bin=codex_bin,
                        timeout_s=lim,
                        gui_driver=gui_driver,
                        max_cua_calls=max_cua,
                        shared_timeline=shared_tl,
                        timeline_lock=tl_lock,
                        barrier=None,
                    )
            wall_s = round(time.monotonic() - t0, 2)
        finally:
            grade_res = desk.stop_and_grade(wall_override_s=round(time.monotonic() - t0, 2))
        contention_tel = summarize_ec2_telemetry(shared_tl, (ra, rb), bridges.get(ra), bridges.get(rb))
        write_json(cond_dir / "shared_timeline.json", shared_tl)

    awareness = analyze_race_awareness(cond_dir, (ra, rb))
    aware_cnt = sum(1 for rv in (awareness.get("roles") or {}).values() if rv.get("explicit_race_mentions", 0) > 0)

    tot_in_tok = sum(int(((actors[r].get("usage") or {}).get("input_tokens") or 0)) for r in (ra, rb))
    tot_out_tok = sum(int(((actors[r].get("usage") or {}).get("output_tokens") or 0)) for r in (ra, rb))
    tot_gui_act = sum(int(actors[r].get("gui_action_calls", 0)) for r in (ra, rb))
    tot_gui_obs = sum(int(actors[r].get("gui_observation_calls", 0)) for r in (ra, rb))
    tot_cli = sum(int(actors[r].get("cli_calls", 0)) for r in (ra, rb))

    rep = {
        "task_id": task_id,
        "title": meta["title"],
        "domain": meta["domain"],
        "track": meta["track"],
        "workspace_mode": meta["workspace_mode"],
        "mode": mode,
        "gui_driver": gui_driver,
        "model": api_cfg.get("model"),
        "effort": api_cfg.get("reasoning_effort"),
        "wall_seconds": wall_s,
        "role_wall_seconds": {r: actors[r]["wall_seconds"] for r in (ra, rb)},
        "score_a": grade_res["score_a"],
        "score_b": grade_res["score_b"],
        "mean_score": grade_res["mean_score"],
        "pass_a": grade_res["pass_a"],
        "pass_b": grade_res["pass_b"],
        "joint_pass": grade_res["joint_pass"],
        "gui_action_calls": tot_gui_act,
        "gui_observation_calls": tot_gui_obs,
        "cli_calls": tot_cli,
        "input_tokens_total": tot_in_tok,
        "output_tokens_total": tot_out_tok,
        "contention_telemetry": contention_tel,
        "explicit_race_aware_roles_count": aware_cnt,
        "race_awareness": awareness,
        "actors": actors,
        "grade": grade_res,
    }
    write_json(cond_dir / "report.json", rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    os.umask(0o000)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("self_validate", "isolated", "seq_ab", "seq_ba", "shared"), default="self_validate")
    ap.add_argument("--gui-driver", choices=("qwen_cua", "xdotool"), default="qwen_cua")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--code-root", type=Path, required=True)
    ap.add_argument("--api-json", type=Path, default=None)
    ap.add_argument("--codex-bin", type=Path, default=Path("/codex/codex"))
    ap.add_argument("--effort", default="high")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--tasks", nargs="*", default=[m["id"] for m in RBS_CATALOG])
    args = ap.parse_args(argv)

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    code_root = args.code_root.resolve()
    task_list = list(args.tasks)

    if args.mode == "self_validate":
        res = {}
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            fmap = {pool.submit(self_validate_rbs_case, tid, out_dir, code_root): tid for tid in task_list}
            for fut in as_completed(fmap):
                tid = fmap[fut]
                try:
                    r = fut.result()
                except Exception as exc:
                    print(f"RBS_SV_ERROR {tid}: {exc}", flush=True)
                    res[tid] = {"task_id": tid, "all_5_gates_valid": False, "error": str(exc)}
                    continue
                res[tid] = r
                print(
                    f"RBS_VALIDATED {tid}: all_5_gates={r['all_5_gates_valid']} "
                    f"(pristine={r['gate1_pristine_score']}, seq_ab={r['gate2_seq_ab_score']}, "
                    f"seq_ba={r['gate3_seq_ba_score']}, contention={r['gate4_contention_score']}, "
                    f"careful_conc={r['gate5_careful_conc_score']} in {r['gate5_careful_conc_seconds']}s)",
                    flush=True,
                )
        all_ok = all(v["all_5_gates_valid"] for v in res.values())
        write_json(out_dir / "SELF_VALIDATION_5GATE_SUMMARY.json", {"all_5_gates_valid": all_ok, "cases": dict(sorted(res.items()))})
        return 0 if all_ok else 1

    assert args.api_json is not None, "--api-json required for model modes"
    api_cfg = json.loads(args.api_json.read_text(encoding="utf-8"))
    api_cfg["reasoning_effort"] = args.effort
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        fmap = {
            pool.submit(run_rbs_case, tid, args.mode, out_dir, code_root, api_cfg, args.codex_bin.resolve(), args.gui_driver): tid
            for tid in task_list
        }
        for fut in as_completed(fmap):
            tid = fmap[fut]
            rep = fut.result()
            results[tid] = rep
            ct = rep["contention_telemetry"]
            print(
                f"DONE {tid} [{rep['mode']}|{rep['model']}]: mean_score={rep['mean_score']} "
                f"(A={rep['score_a']}, B={rep['score_b']}, joint={rep['joint_pass']}) "
                f"GUI={rep['gui_action_calls']+rep['gui_observation_calls']} CLI={rep['cli_calls']} "
                f"tok={rep['input_tokens_total']} flips={ct['focus_flips']} miskey={ct['misrouted_keystrokes']} "
                f"ov={ct['overlap_seconds']}s wall={rep['wall_seconds']}s",
                flush=True,
            )
            write_json(
                out_dir / f"SUMMARY_{args.mode}_{api_cfg.get('model','model')}.json",
                {
                    "mode": args.mode,
                    "model": api_cfg.get("model"),
                    "effort": args.effort,
                    "gui_driver": args.gui_driver,
                    "mean_score_avg": round(sum(v["mean_score"] for v in results.values()) / max(1, len(results)), 4),
                    "joint_pass_count": sum(1 for v in results.values() if v["joint_pass"]),
                    "total_tasks": len(results),
                    "results": dict(sorted(results.items())),
                },
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
