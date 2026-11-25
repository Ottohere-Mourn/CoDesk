"""Unified multi-driver runner & 5-gate validator for the curated 8-case suite (curated_8cases_v1).

Covers the 8 reviewed high-quality cases:
  - RBS3-04, RBS3-05, RBS3-02, RBS2-06, RBS-06, RBS3-01 (ec_v2_multi_driver_desktop)
  - EC-01, EC-03 (ec_v1_astra_desktop)

Key harness properties:
  - Unlimited GUI/CLI steps (max_cua_calls = None) with a >= 7200s (2h+) outer anti-deadlock timeout.
  - Standardized default reasoning effort = 'high' across all evaluated models.
  - Read-only stop_and_grade() (never injects post-exit save keystrokes into open windows).
  - Supports strict CLI-from-X11 isolation (--isolate-cli-from-x11) for clean GUI-driver ablations.
  - Shares --pid container:<desk> when required by live local service tasks (e.g. RBS3-05 :19515).
  - Completes absent-peer reference state in isolated single-agent runs on shared-workspace cases
    so isolated baselines are never penalized for an absent peer's open document or covenant leg.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any

from experiments.deepseek_v41_eval import analyze_race_awareness
from experiments.exam_contention_v1 import (
    ExamContentionDesktop,
    run_exam_actor,
)
from experiments.exam_contention_v2 import (
    DESKTOP_IMAGE as EC2_DESKTOP_IMAGE,
    ExamV2Desktop,
    RoleMcpBridge,
    _run_desk_reg,
    run_ec2_actor,
    summarize_ec2_telemetry,
)
from tasks.curated_8cases_v1.registry import (
    CURATED_8_BY_ID,
    CURATED_8_IDS,
)
from tasks.rb_osw2_synth_v3.common import read_json_safe, write_json

CURATED_REGISTRY_MOD = "tasks.curated_8cases_v1.registry"
CURATED_EXTRA_PKGS: tuple[str, ...] = (
    "tasks/exam_contention_v1",
    "tasks/rb_osw2_synth_v1",
    "tasks/rb_osw2_synth_v2",
    "tasks/rb_osw2_synth_v3",
    "tasks/curated_8cases_v1",
)

READONLY_UNO_PROBE_PY = """
import pathlib, sys
target_path = pathlib.Path(sys.argv[1]).resolve()
out_flag = pathlib.Path(sys.argv[2])
try:
    import uno  # type: ignore
    local_ctx = uno.getComponentContext()
    resolver = local_ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local_ctx)
    ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext")
    desk = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    comps = desk.getComponents().createEnumeration()
    dirty = False
    while comps.hasMoreElements():
        doc = comps.nextElement()
        url = getattr(doc, "getURL", lambda: "")() or ""
        if target_path.name in url and getattr(doc, "isModified", lambda: False)():
            dirty = True
            break
    out_flag.write_text("1" if dirty else "0")
except Exception:
    out_flag.write_text("0")
""".strip()


def build_curated_agent_prompt(ticket_md: str) -> str:
    """Minimal neutral wrapper: states workspace & available tool servers with zero step caps or countdown pressure."""
    b = "`"
    return (
        f"Workstation environment (1920x1080 Linux desktop, workspace {b}/workspace{b}):\n"
        "- Use the Desktop GUI MCP tools to inspect and interact with live desktop windows.\n"
        f"- Use {b}guest_bash{b} to run shell commands, scripts, compilers, and local tools in {b}/workspace{b}.\n"
        "- Save any edits made inside open desktop applications before finishing.\n\n"
        f"{ticket_md}\n"
    )


class CuratedV2Desktop(ExamV2Desktop):
    """Hardened ExamV2Desktop subclass with PID namespace sharing, clean CLI isolation, and read-only grading."""

    def __init__(
        self,
        cond_dir: Path,
        task_id: str,
        code_root: Path,
        active_roles: tuple[str, ...] | None = None,
        isolate_cli_from_x11: bool = False,
        record_video: bool = False,
    ) -> None:
        super().__init__(
            cond_dir=cond_dir,
            task_id=task_id,
            code_root=code_root,
            active_roles=active_roles,
            record_video=record_video,
            registry_module=CURATED_REGISTRY_MOD,
            meta_map=CURATED_8_BY_ID,
            extra_task_packages=CURATED_EXTRA_PKGS,
        )
        self.isolate_cli_from_x11 = isolate_cli_from_x11

    def start(self) -> None:
        super().start()
        if not (self.meta.get("share_desk_pid") or self.isolate_cli_from_x11):
            return
        for r_idx, r_name in enumerate(self.active_roles):
            old_rc = self.role_containers.get(r_name)
            if old_rc:
                subprocess.run(["docker", "rm", "-f", old_rc], capture_output=True, timeout=20)
            rc_name = f"{self.container_name}-r{r_idx}"
            role_ws = (self.ws_root / r_name) if self.meta["workspace_mode"] == "isolated" else (self.ws_root / "shared")
            role_ws.mkdir(parents=True, exist_ok=True)
            vol_args = [
                "-v", f"{role_ws}:/workspace",
                "-v", f"{self.dl_vol}:/home/user/Downloads",
                "-v", f"{self.lo_vol}:/home/user/.config",
            ]
            if not self.isolate_cli_from_x11:
                vol_args = ["--volumes-from", self.container_name, "-v", f"{role_ws}:/workspace"]
            pid_args = ["--pid", f"container:{self.container_name}"] if self.meta.get("share_desk_pid") else []
            subprocess.run(
                [
                    "docker", "run", "-d", "--name", rc_name,
                    "--cpus", "3", "--memory", "6g", "--shm-size", "512m",
                    "--security-opt", "no-new-privileges",
                    "--network", f"container:{self.container_name}",
                    "--ipc", f"container:{self.container_name}",
                    *pid_args,
                    "--label", "org.paragui.kind=curated-8cases-role",
                    *vol_args,
                    EC2_DESKTOP_IMAGE, "sleep", "infinity",
                ],
                check=True, capture_output=True, text=True, timeout=60,
            )
            self.role_containers[r_name] = rc_name
            subprocess.run(
                [
                    "docker", "exec", rc_name, "bash", "-lc",
                    "id -u user >/dev/null 2>&1 || useradd -m -u 1000 -g 0 -s /bin/bash user; "
                    "mkdir -p /home/user/work && chown -R 1000:0 /home/user",
                ],
                check=True, capture_output=True, timeout=20,
            )

    def exec_role(self, role: str, command_str: str, cwd: str = "/workspace", timeout_s: int = 200) -> dict[str, Any]:
        if not self.isolate_cli_from_x11:
            return super().exec_role(role, command_str, cwd=cwd, timeout_s=timeout_s)
        target_ctr = self.role_containers.get(role, self.container_name)
        jdir = f"/tmp/work_{role.lower()}"
        try:
            cp = subprocess.run(
                [
                    "docker", "exec", "--user", "1000:0", "-w", cwd,
                    "-e", "HOME=/home/user",
                    "-e", "PATH=/usr/local/bin:/usr/bin:/bin",
                    "-e", "LANG=C.UTF-8",
                    "-e", "HISTFILE=/dev/null",
                    "-e", f"TMPDIR={jdir}",
                    target_ctr, "bash", "-lc", f"mkdir -p {jdir}; umask 0002; " + command_str,
                ],
                capture_output=True, text=True, timeout=timeout_s,
            )
            return {"ok": cp.returncode == 0, "returncode": cp.returncode, "stdout": cp.stdout[-12000:], "stderr": cp.stderr[-6000:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "returncode": 124, "stdout": "", "stderr": f"Timed out after {timeout_s}s"}
        finally:
            subprocess.run(["docker", "exec", self.container_name, "chmod", "-R", "a+rX,ug+w", "/ws_root"], capture_output=True, timeout=15)

    def stop_and_grade(self, wall_override_s: float = 0.0) -> dict[str, Any]:
        """Read-only grading without injecting post-exit save keystrokes into open GUI apps."""
        grade_out = self.cond_dir / "grade.json"
        try:
            if self.created:
                split_brain = False
                subprocess.run(
                    ["docker", "exec", "-i", self.container_name, "bash", "-lc", "cat > /opt/ec2_state/readonly_uno_probe.py"],
                    input=READONLY_UNO_PROBE_PY.encode("utf-8"),
                    capture_output=True,
                    timeout=10,
                )
                for idx, (doc_p, _tag, _kind, *_rest) in enumerate(self.meta.get("open_gui_docs") or ()):
                    flag_p = f"/tmp/_uno_dirty_{idx}"
                    subprocess.run(
                        [
                            "docker", "exec", "--user", "1000:0", self.container_name,
                            "python3", "/opt/ec2_state/readonly_uno_probe.py", str(doc_p), flag_p,
                        ],
                        capture_output=True,
                        timeout=10,
                    )
                    chk = subprocess.run(
                        ["docker", "exec", self.container_name, "bash", "-lc", f"cat {flag_p} 2>/dev/null || echo 0"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if chk.stdout.strip() == "1":
                        split_brain = True

                subprocess.run(["docker", "cp", f"{self.container_name}:/opt/ec2_state/service_state.json", str(self.service_state_out)], capture_output=True, timeout=15)
                sdata = read_json_safe(self.service_state_out)
                sdata.setdefault("open_gui_split_brain", split_brain)
                write_json(self.service_state_out, sdata)
                subprocess.run(["docker", "cp", str(self.service_state_out), f"{self.container_name}:/opt/ec2_state/service_state.json"], capture_output=True, timeout=15)

                subprocess.run(
                    [
                        "docker", "exec", "-e", "PYTHONPATH=/opt/ec2_state/pkg",
                        self.container_name, "python3", "-m", self.registry_module, "grade",
                        "--task", self.task_id, "--workspace-root", "/ws_root",
                        "--state-file", "/opt/ec2_state/service_state.json",
                        "--wall-seconds", str(round(wall_override_s, 2)),
                        "--out", "/opt/ec2_state/grade.json",
                    ],
                    check=True, capture_output=True, text=True, timeout=240,
                )
                subprocess.run(["docker", "cp", f"{self.container_name}:/opt/ec2_state/grade.json", str(grade_out)], check=True, capture_output=True, timeout=20)
        finally:
            for rc in list(self.role_containers.values()):
                subprocess.run(["docker", "rm", "-f", rc], capture_output=True, timeout=25)
            self.role_containers.clear()
            if self.created:
                subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=30)
                self.created = False
            for v in (self.x11_vol, self.xdg_vol, self.dl_vol, self.lo_vol):
                subprocess.run(["docker", "volume", "rm", "-f", v], capture_output=True, timeout=15)
        return json.loads(grade_out.read_text(encoding="utf-8"))


def _grade_ec1_readonly(desk: ExamContentionDesktop, task_id: str, wall_s: float) -> dict[str, Any]:
    """Grade EC-01 / EC-03 inside container without post-exit save keystrokes."""
    grade_out = desk.cond_dir / "grade.json"
    try:
        if desk.created:
            for pkg in ("curated_8cases_v1", "rb_osw2_synth_v1", "rb_osw2_synth_v2", "rb_osw2_synth_v3"):
                subprocess.run(["docker", "cp", str(desk.code_root / "tasks" / pkg), f"{desk.container_name}:/opt/ec_state/pkg/tasks/{pkg}"], check=True, capture_output=True, timeout=20)
            subprocess.run(
                [
                    "docker", "exec", desk.container_name, "bash", "-lc",
                    "mkdir -p /ws_root && ln -sfn /workspace /ws_root/shared",
                ],
                check=True, capture_output=True, timeout=10,
            )
            subprocess.run(
                [
                    "docker", "exec", "-e", "PYTHONPATH=/opt/ec_state/pkg",
                    desk.container_name, "python3", "-m", CURATED_REGISTRY_MOD, "grade",
                    "--task", task_id, "--workspace-root", "/ws_root",
                    "--state-file", "/opt/ec_state/service_state.json",
                    "--wall-seconds", str(round(wall_s, 2)),
                    "--out", "/opt/ec_state/grade.json",
                ],
                check=True, capture_output=True, text=True, timeout=240,
            )
            subprocess.run(["docker", "cp", f"{desk.container_name}:/opt/ec_state/grade.json", str(grade_out)], check=True, capture_output=True, timeout=20)
    finally:
        for rc in list(desk.role_containers.values()):
            subprocess.run(["docker", "rm", "-f", rc], capture_output=True, timeout=25)
        desk.role_containers.clear()
        if desk.created:
            subprocess.run(["docker", "rm", "-f", desk.container_name], capture_output=True, timeout=30)
            desk.created = False
    return json.loads(grade_out.read_text(encoding="utf-8"))


def self_validate_curated_case(task_id: str, out_dir: Path, code_root: Path) -> dict[str, Any]:
    """Run 5-gate deterministic check (including Gate 5 careful_conc concurrent feasibility)."""
    meta = CURATED_8_BY_ID[task_id]
    ra, rb = meta["roles"]
    cdir = out_dir / task_id
    cdir.mkdir(parents=True, exist_ok=True)
    conc_budget = float(meta["conc_role_timeout_s"])

    if meta["runner_family"] == "ec_v1_astra_desktop":
        def _mk(sub_name: str) -> ExamContentionDesktop:
            d = ExamContentionDesktop(cdir / sub_name, task_id, code_root, record_video=False)
            d.build_pristine()
            return d

        d1 = _mk("gate1_pristine")
        d1.start()
        g1 = _grade_ec1_readonly(d1, task_id, 1.0)

        d2 = _mk("gate2_seq_ab")
        d2.start()
        for r in (ra, rb):
            subprocess.run(["docker", "exec", "-e", "PYTHONPATH=/opt/ec_state/pkg", d2.container_name, "python3", "-m", "tasks.exam_contention_v1.registry", "solve_role", "--task", task_id, "--role", r, "--workspace", "/workspace"], check=True, capture_output=True, timeout=180)
        g2 = _grade_ec1_readonly(d2, task_id, 5.0)

        d3 = _mk("gate3_seq_ba")
        d3.start()
        for r in (rb, ra):
            subprocess.run(["docker", "exec", "-e", "PYTHONPATH=/opt/ec_state/pkg", d3.container_name, "python3", "-m", "tasks.exam_contention_v1.registry", "solve_role", "--task", task_id, "--role", r, "--workspace", "/workspace"], check=True, capture_output=True, timeout=180)
        g3 = _grade_ec1_readonly(d3, task_id, 5.0)

        d4 = _mk("gate4_contention")
        d4.start()
        subprocess.run(["docker", "exec", "-e", "PYTHONPATH=/opt/ec_state/pkg", d4.container_name, "python3", "-m", "tasks.exam_contention_v1.registry", "sim_naive_race", "--task", task_id, "--workspace", "/workspace"], check=True, capture_output=True, timeout=180)
        g4 = _grade_ec1_readonly(d4, task_id, 5.0)

        d5 = _mk("gate5_careful_conc")
        d5.start()
        t5_0 = time.monotonic()
        subprocess.run(["docker", "exec", "-e", "PYTHONPATH=/opt/ec_state/pkg", d5.container_name, "python3", "-m", "tasks.exam_contention_v1.registry", "sim_careful_conc", "--task", task_id, "--workspace", "/workspace"], check=True, capture_output=True, timeout=240)
        t5_s = round(time.monotonic() - t5_0, 2)
        g5 = _grade_ec1_readonly(d5, task_id, t5_s)
    else:
        def _mk_v2(sub_name: str) -> CuratedV2Desktop:
            d = CuratedV2Desktop(cdir / sub_name, task_id, code_root)
            d.build_pristine()
            return d

        d1 = _mk_v2("gate1_pristine")
        try:
            d1.start()
        finally:
            g1 = d1.stop_and_grade()

        d2 = _mk_v2("gate2_seq_ab")
        try:
            d2.start()
            _run_desk_reg(d2, ["solve_role", "--task", task_id, "--role", ra, "--workspace-root", "/ws_root"])
            _run_desk_reg(d2, ["solve_role", "--task", task_id, "--role", rb, "--workspace-root", "/ws_root"])
        finally:
            g2 = d2.stop_and_grade()

        d3 = _mk_v2("gate3_seq_ba")
        try:
            d3.start()
            _run_desk_reg(d3, ["solve_role", "--task", task_id, "--role", rb, "--workspace-root", "/ws_root"])
            _run_desk_reg(d3, ["solve_role", "--task", task_id, "--role", ra, "--workspace-root", "/ws_root"])
        finally:
            g3 = d3.stop_and_grade()

        d4 = _mk_v2("gate4_contention")
        try:
            d4.start()
            _run_desk_reg(d4, ["sim_contention", "--task", task_id, "--workspace-root", "/ws_root", "--state-dir", "/opt/ec2_state"])
        finally:
            g4 = d4.stop_and_grade()

        d5 = _mk_v2("gate5_careful_conc")
        t5_0 = time.monotonic()
        t5_s = 9999.0
        try:
            d5.start()
            t5_0 = time.monotonic()
            _run_desk_reg(d5, ["careful_conc", "--task", task_id, "--workspace-root", "/ws_root"])
            t5_s = round(time.monotonic() - t5_0, 2)
        finally:
            g5 = d5.stop_and_grade(wall_override_s=t5_s)

    gate4_active = (g4["joint_pass"] is False) or (float(g4.get("mean_score", 0.0)) < 0.96)
    all_ok = (
        g1["joint_pass"] is False
        and g2["joint_pass"] is True
        and g3["joint_pass"] is True
        and gate4_active
        and g5["joint_pass"] is True
        and t5_s <= 0.55 * conc_budget
    )
    return {
        "task_id": task_id,
        "runner_family": meta["runner_family"],
        "gate1_pristine_pass": g1["joint_pass"],
        "gate2_seq_ab_pass": g2["joint_pass"],
        "gate3_seq_ba_pass": g3["joint_pass"],
        "gate4_contention_joint_pass": g4["joint_pass"],
        "gate5_careful_conc_pass": g5["joint_pass"],
        "gate5_careful_conc_seconds": t5_s,
        "gate5_within_55pct_budget": t5_s <= 0.55 * conc_budget,
        "all_5_gates_valid": all_ok,
    }


def run_curated_episode(
    task_id: str,
    mode: str,
    gui_driver: str,
    isolate_cli_from_x11: bool,
    model_name: str,
    effort: str,
    api_cfg: dict[str, str],
    codex_bin: Path,
    out_dir: Path,
    code_root: Path,
) -> dict[str, Any]:
    assert mode in ("isolated", "seq_ab", "shared")
    meta = CURATED_8_BY_ID[task_id]
    ra, rb = meta["roles"]
    timeout_s = int(meta["iso_role_timeout_s"] if mode in ("isolated", "seq_ab") else meta["conc_role_timeout_s"])
    unbounded_cua = int(meta["max_cua_calls"]) if meta.get("max_cua_calls") else sys.maxsize
    cond_dir = out_dir / f"{task_id}_{model_name}_{gui_driver}_{mode}"
    cond_dir.mkdir(parents=True, exist_ok=True)

    if meta["runner_family"] == "ec_v1_astra_desktop":
        if mode == "isolated":
            role_runs: dict[str, Any] = {}
            role_grades: dict[str, Any] = {}
            for idx, r in enumerate((ra, rb)):
                peer = rb if idx == 0 else ra
                r_dir = cond_dir / f"iso_{r}"
                desk = ExamContentionDesktop(r_dir, task_id, code_root, record_video=False)
                desk.build_pristine()
                t0 = time.monotonic()
                desk.start()
                t_md = (desk.tickets_root / r / "task.md").read_text(encoding="utf-8")
                prompt = build_curated_agent_prompt(t_md)
                role_runs[r] = run_exam_actor(r, prompt, desk, model_name, effort, api_cfg, codex_bin, r_dir / "actors" / r, timeout_s)
                subprocess.run(
                    [
                        "docker", "exec", "-e", "PYTHONPATH=/opt/ec_state/pkg",
                        desk.container_name, "python3", "-m", "tasks.exam_contention_v1.registry",
                        "solve_role", "--task", task_id, "--role", peer, "--workspace", "/workspace",
                    ],
                    check=False, capture_output=True, timeout=180,
                )
                role_grades[r] = _grade_ec1_readonly(desk, task_id, time.monotonic() - t0)
            ga, gb = role_grades[ra], role_grades[rb]
            sa = 1.0 if ga["pass_a"] else 0.0
            sb = 1.0 if gb["pass_b"] else 0.0
            res_out = {
                "task_id": task_id,
                "model": model_name,
                "mode": mode,
                "gui_driver": gui_driver,
                "pass_a": bool(ga["pass_a"]),
                "pass_b": bool(gb["pass_b"]),
                "score_a": sa,
                "score_b": sb,
                "mean_score": round(0.5 * (sa + sb), 4),
                "joint_pass": bool(ga["pass_a"] and gb["pass_b"]),
                "role_runs": role_runs,
                "isolated_role_grades": role_grades,
            }
            write_json(cond_dir / "episode_result.json", res_out)
            return res_out

        desk = ExamContentionDesktop(cond_dir, task_id, code_root, record_video=(mode == "shared"))
        desk.build_pristine()
        t0 = time.monotonic()
        desk.start()
        prompts = {r: build_curated_agent_prompt((desk.tickets_root / r / "task.md").read_text(encoding="utf-8")) for r in (ra, rb)}
        role_runs = {}
        if mode == "seq_ab":
            for r in (ra, rb):
                role_runs[r] = run_exam_actor(r, prompts[r], desk, model_name, effort, api_cfg, codex_bin, cond_dir / "actors" / r, timeout_s)
        else:
            bar = threading.Barrier(2)

            def _go_ec(r: str) -> tuple[str, dict[str, Any]]:
                try:
                    bar.wait(timeout=45)
                except threading.BrokenBarrierError:
                    pass
                return r, run_exam_actor(r, prompts[r], desk, model_name, effort, api_cfg, codex_bin, cond_dir / "actors" / r, timeout_s)

            with ThreadPoolExecutor(max_workers=2) as pool:
                for fut in as_completed([pool.submit(_go_ec, ra), pool.submit(_go_ec, rb)]):
                    rk, rv = fut.result()
                    role_runs[rk] = rv
        grade = _grade_ec1_readonly(desk, task_id, time.monotonic() - t0)
        res_out = {
            "task_id": task_id,
            "model": model_name,
            "mode": mode,
            "gui_driver": gui_driver,
            "grade": grade,
            "mean_score": grade["mean_score"],
            "joint_pass": grade["joint_pass"],
            "role_runs": role_runs,
        }
        write_json(cond_dir / "episode_result.json", res_out)
        return res_out

    if mode == "isolated":
        role_runs_v2: dict[str, Any] = {}
        role_grades_v2: dict[str, Any] = {}
        for idx, r in enumerate((ra, rb)):
            peer = rb if idx == 0 else ra
            r_dir = cond_dir / f"iso_{r}"
            desk_v2 = CuratedV2Desktop(r_dir, task_id, code_root, active_roles=(r,), isolate_cli_from_x11=isolate_cli_from_x11)
            desk_v2.build_pristine()
            t0 = time.monotonic()
            try:
                desk_v2.start()
                t_md = (desk_v2.tickets_root / r / "task.md").read_text(encoding="utf-8")
                prompt = build_curated_agent_prompt(t_md)
                tl: list[dict[str, Any]] = []
                br = RoleMcpBridge(desk_v2, r, gui_driver, unbounded_cua, tl, threading.Lock(), t0)
                role_runs_v2[r] = run_ec2_actor(r, prompt, br, model_name, effort, api_cfg, codex_bin, r_dir / "actors" / r, timeout_s)
                if meta.get("absent_peer_reference_fill_in_isolated"):
                    _run_desk_reg(desk_v2, ["solve_role", "--task", task_id, "--role", peer, "--workspace-root", "/ws_root"])
            finally:
                role_grades_v2[r] = desk_v2.stop_and_grade(wall_override_s=round(time.monotonic() - t0, 2))
        sa = float(role_grades_v2[ra]["score_a"])
        sb = float(role_grades_v2[rb]["score_b"])
        ja = bool(role_grades_v2[ra]["pass_a"])
        jb = bool(role_grades_v2[rb]["pass_b"])
        res_out = {
            "task_id": task_id,
            "model": model_name,
            "mode": mode,
            "gui_driver": gui_driver,
            "score_a": round(sa, 4),
            "score_b": round(sb, 4),
            "mean_score": round(0.5 * (sa + sb), 4),
            "joint_pass": bool(ja and jb),
            "role_runs": role_runs_v2,
            "isolated_role_grades": role_grades_v2,
        }
        write_json(cond_dir / "episode_result.json", res_out)
        return res_out

    desk_sh = CuratedV2Desktop(cond_dir, task_id, code_root, active_roles=(ra, rb), isolate_cli_from_x11=isolate_cli_from_x11)
    desk_sh.build_pristine()
    tl_sh: list[dict[str, Any]] = []
    tl_lock = threading.Lock()
    t0 = time.monotonic()
    role_runs_sh: dict[str, Any] = {}
    try:
        desk_sh.start()
        prompts_sh = {r: build_curated_agent_prompt((desk_sh.tickets_root / r / "task.md").read_text(encoding="utf-8")) for r in (ra, rb)}
        if mode == "seq_ab":
            for r in (ra, rb):
                br = RoleMcpBridge(desk_sh, r, gui_driver, unbounded_cua, tl_sh, tl_lock, t0)
                role_runs_sh[r] = run_ec2_actor(r, prompts_sh[r], br, model_name, effort, api_cfg, codex_bin, cond_dir / "actors" / r, timeout_s)
        else:
            bar = threading.Barrier(2)

            def _go_v2(r: str) -> tuple[str, dict[str, Any]]:
                br = RoleMcpBridge(desk_sh, r, gui_driver, unbounded_cua, tl_sh, tl_lock, t0)
                try:
                    bar.wait(timeout=45)
                except threading.BrokenBarrierError:
                    pass
                return r, run_ec2_actor(r, prompts_sh[r], br, model_name, effort, api_cfg, codex_bin, cond_dir / "actors" / r, timeout_s)

            with ThreadPoolExecutor(max_workers=2) as pool:
                for fut in as_completed([pool.submit(_go_v2, ra), pool.submit(_go_v2, rb)]):
                    rk, rv = fut.result()
                    role_runs_sh[rk] = rv
        wall_s = round(time.monotonic() - t0, 2)
    finally:
        grade_sh = desk_sh.stop_and_grade(wall_override_s=round(time.monotonic() - t0, 2))

    tel = summarize_ec2_telemetry(tl_sh, (ra, rb))
    aware = analyze_race_awareness(cond_dir, (ra, rb))
    res_out = {
        "task_id": task_id,
        "model": model_name,
        "mode": mode,
        "gui_driver": gui_driver,
        "wall_seconds": wall_s,
        "grade": grade_sh,
        "mean_score": grade_sh["mean_score"],
        "joint_pass": grade_sh["joint_pass"],
        "telemetry_summary": tel,
        "race_awareness": aware,
        "role_runs": role_runs_sh,
    }
    write_json(cond_dir / "episode_result.json", res_out)
    return res_out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("self_validate", "isolated", "seq_ab", "shared"), required=True)
    ap.add_argument("--tasks", default="all", help="Comma-separated curated IDs or 'all'")
    ap.add_argument("--gui-driver", choices=("qwen_cua", "xdotool"), default="qwen_cua")
    ap.add_argument("--isolate-cli-from-x11", action="store_true", help="Strip X11/AT-SPI sockets from role CLI containers for strict CUA-driver ablations")
    ap.add_argument("--model", default="gpt-6.1-sol")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--api-json", type=Path, default=None)
    ap.add_argument("--codex-bin", type=Path, default=Path("/home/yuke/data/paraGUI/runtime/codex/codex"))
    ap.add_argument("--code-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)

    selected = list(CURATED_8_IDS) if args.tasks.strip().lower() == "all" else [t.strip() for t in args.tasks.split(",") if t.strip()]
    unknown = [t for t in selected if t not in CURATED_8_BY_ID]
    if unknown:
        raise SystemExit(f"Unknown curated task IDs: {unknown}; valid={list(CURATED_8_IDS)}")
    args.out.mkdir(parents=True, exist_ok=True)

    if args.mode == "self_validate":
        rep: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=min(args.workers, len(selected))) as pool:
            futs = {pool.submit(self_validate_curated_case, tid, args.out, args.code_root.resolve()): tid for tid in selected}
            for fut in as_completed(futs):
                tid = futs[fut]
                rep[tid] = fut.result()
                print(f"[SELF-VALIDATE] {tid}: all_5_gates_valid={rep[tid]['all_5_gates_valid']} (gate5={rep[tid]['gate5_careful_conc_seconds']}s)", flush=True)
        summary = {
            "suite": "curated_8cases_v1",
            "total_cases": len(selected),
            "all_5_gates_valid": all(v["all_5_gates_valid"] for v in rep.values()),
            "cases": {tid: rep[tid] for tid in selected},
        }
        write_json(args.out / "curated_8cases_self_validation.json", summary)
        return 0 if summary["all_5_gates_valid"] else 1

    if not args.api_json or not args.api_json.is_file():
        raise SystemExit("--api-json is required for live model modes")
    api_cfg = json.loads(args.api_json.read_text(encoding="utf-8"))
    episodes: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=min(args.workers, len(selected))) as pool:
        futs = {
            pool.submit(
                run_curated_episode,
                tid,
                args.mode,
                args.gui_driver,
                args.isolate_cli_from_x11,
                args.model,
                args.effort,
                api_cfg,
                args.codex_bin,
                args.out,
                args.code_root.resolve(),
            ): tid
            for tid in selected
        }
        for fut in as_completed(futs):
            tid = futs[fut]
            episodes[tid] = fut.result()
            print(f"[{args.mode.upper()}] {tid}: mean_score={episodes[tid].get('mean_score')} joint_pass={episodes[tid].get('joint_pass')}", flush=True)
    write_json(args.out / f"curated_8cases_{args.model}_{args.gui_driver}_{args.mode}.json", {"suite": "curated_8cases_v1", "episodes": episodes})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
