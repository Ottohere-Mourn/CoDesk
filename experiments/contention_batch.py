"""Bounded queue and paired report for the original-OSWorld contention comparison."""
from __future__ import annotations

import argparse
import csv
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from experiments.freehand_vm10 import save


def jobs_for(manifest):
    jobs = []
    for index, case in enumerate(manifest["cases"]):
        first, second = ("codex", "freehand") if index % 2 == 0 else ("freehand", "codex")
        for harness, mode in [(first, "parallel"), (second, "parallel"),
                              (second, "sequential"), (first, "sequential")]:
            jobs.append({"name": f"{case['name']}-{harness}-{mode}", "pair": case["name"],
                         "harness": harness, "mode": mode, "status": "pending"})
    return jobs


def trial_summary(directory):
    path = directory / "result.json"
    if not path.exists():
        return None
    result = json.loads(path.read_text())
    values = list((result.get("scores") or {}).values())
    finite = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    complete = len(values) == 2 and len(finite) == 2
    agents = result.get("agents", {})
    preparation_error = any(a.get("status") == "error" and not a.get("model_requests")
                            and not a.get("model_responses") for a in agents.values())
    review_path = directory / "infrastructure-review.json"
    review = json.loads(review_path.read_text()) if review_path.exists() else {}
    reviewed_interruption = bool(review.get("exclude_from_comparison"))
    measurable = complete and not preparation_error and not reviewed_interruption
    usage = {key: sum((a.get("usage") or {}).get(key) or 0 for a in agents.values())
             for key in ["input_tokens", "output_tokens", "total_tokens"]}
    states = [json.loads(p.read_text()) for p in directory.glob("agent*/state.json")]
    overlap = (max(0, min(s.get("finished_at", 0) for s in states) -
                   max(s.get("started_at", 0) for s in states)) if len(states) == 2 else None)
    return {"scores": result.get("scores"), "mean_score": sum(finite) / 2 if measurable else None,
            "joint_pass": all(s >= 0.999 for s in finite) if measurable else None,
            "valid_scores": len(finite) if not (preparation_error or reviewed_interruption) else 0,
            "measurement_valid": measurable,
            "invalid_reason": ("preparation_error_before_model" if preparation_error else
                               "reviewed_guest_control_interruption" if reviewed_interruption else None),
            "infrastructure_review": review or None,
            "error": result.get("error"),
            "eval_errors": result.get("eval_errors"),
            "agent_errors": {name: a.get("error") for name, a in agents.items() if a.get("error")},
            "agent_statuses": {name: a.get("status") for name, a in agents.items()},
            "api_errors": sum(len(a.get("api_errors", [])) for a in agents.values()),
            "model_requests": sum(a.get("model_requests", 0) for a in agents.values()),
            "usage": usage if any(a.get("usage") for a in agents.values()) else None,
            "total_s": result.get("total_s"), "agents_s": result.get("agents_s"),
            "session_overlap_s": overlap}


def make_report(project, jobs):
    manifest = json.loads((project / "manifest.json").read_text())
    records = {}
    overrides_path = project / "effective_attempts.json"
    overrides = json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
    for job in jobs:
        original_directory = project / "runs" / job["name"]
        override = overrides.get(job["name"])
        directory = project / override["directory"] if override else original_directory
        if not directory.resolve().is_relative_to(project.resolve()):
            raise ValueError("Recovery directory must be inside this batch")
        summary = trial_summary(directory)
        if summary is not None:
            records[job["name"]] = {**job, **summary, "attempt_directory": str(directory.relative_to(project)),
                "recovered": bool(override), "original_status": job["status"],
                "original_attempt": trial_summary(original_directory) if override else None}
    cases = []
    for case in manifest["cases"]:
        row = {"pair": case["name"], "resource": case["resource"], "conditions": {}}
        for harness in ["codex", "freehand"]:
            for mode in ["parallel", "sequential"]:
                row["conditions"][f"{harness}_{mode}"] = records.get(f"{case['name']}-{harness}-{mode}")
            seq = row["conditions"][f"{harness}_sequential"]
            par = row["conditions"][f"{harness}_parallel"]
            if seq and par and seq["mean_score"] is not None and par["mean_score"] is not None:
                row[harness + "_score_drop"] = seq["mean_score"] - par["mean_score"]
                row[harness + "_contention_candidate"] = bool(seq["joint_pass"] and not par["joint_pass"]
                    and not seq["agent_errors"] and not par["agent_errors"]
                    and not seq["api_errors"] and not par["api_errors"]
                    and not seq["eval_errors"] and not par["eval_errors"])
        cases.append(row)
    conditions = {}
    for harness in ["codex", "freehand"]:
        for mode in ["parallel", "sequential"]:
            values = [r for r in records.values() if r["harness"] == harness and r["mode"] == mode]
            valid = [r for r in values if r["mean_score"] is not None]
            conditions[f"{harness}_{mode}"] = {"trials": len(values), "valid_pairs": len(valid),
                "mean_score": sum(r["mean_score"] for r in valid) / len(valid) if valid else None,
                "joint_passes": sum(bool(r["joint_pass"]) for r in valid),
                "model_requests": sum(r["model_requests"] for r in values),
                "api_errors": sum(r["api_errors"] for r in values)}
    report = {"planned": len(jobs), "finished": sum(j["status"] in ("finished", "error", "timeout") for j in jobs),
              "model": manifest["model"], "conditions": conditions, "cases": cases,
              "valid_conditions": sum(r["measurement_valid"] for r in records.values()),
              "recovered_conditions": sum(r["recovered"] for r in records.values()),
              "updated_at": time.time(), "records": records}
    save(project / "summary.json", report)
    def score(record):
        if record is None:
            return "—"
        return "ERR" if record["mean_score"] is None else f"{record['mean_score']:.2f}"
    lines = ["# OSWorld 原版任务竞争场景：Codex 与 Freehand", "",
        f"完成 {report['finished']}/{len(jobs)} 轮；模型 {manifest['model']}，high，每个 agent 1800 秒。",
        f"有效配对评分 {report['valid_conditions']} 份；补跑后恢复 {report['recovered_conditions']} 个条件。模型启动前的准备失败单列为 ERR，原始记录保留。",
        "每组保留原版任务与评分器，两种 harness 各做一次并发和一次顺序对照。分数为两项任务原版评分的平均值。", "",
        "| 组合 | Codex 顺序 | Codex 并发 | Freehand 顺序 | Freehand 并发 |",
        "|---|---:|---:|---:|---:|"]
    for case in cases:
        c = case["conditions"]
        lines.append("| " + case["pair"] + " | " + " | ".join(score(c[key]) for key in
            ["codex_sequential", "codex_parallel", "freehand_sequential", "freehand_parallel"]) + " |")
    lines += ["", "两种 harness 都允许在 Guest 内使用 Bash、文件、脚本和 GUI。Codex 保留官方 CLI 的原生工具与上下文管理，Freehand 保留原生循环及最近 4 张图片窗口。",
        "每个条件只有一次运行；分数差只用于寻找并发受损候选，需要结合共享文件版本和轨迹核查，不能单凭差值认定竞态。缺失或异常评分单列为 ERR，不当作零分。",
        "", "[完整汇总](summary.json) · [任务与源码清单](manifest.json) · [实时队列](progress.json)",
        "", "Codex 配置参考：[OpenAI 官方配置文档](https://developers.openai.com/codex/config-reference/)。",
        "原始结果、API 记录和 Guest 轨迹位于 runs/ 下对应组合目录；observer.tar.gz 保存焦点记录与共享文件版本。"]
    (project / "REPORT.md").write_text("\n".join(lines) + "\n")
    with (project / "scores.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["pair", "harness", "mode", "score", "joint_pass", "agent_seconds", "model_requests", "api_errors"])
        for r in records.values():
            writer.writerow([r["pair"], r["harness"], r["mode"], r["mean_score"], r["joint_pass"],
                             r["agents_s"], r["model_requests"], r["api_errors"]])
    return report


def available(project):
    memory = {line.split(":")[0]: int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()}
    return memory["MemAvailable"] >= 24 * 1024 * 1024 and shutil.disk_usage(project).free >= 30 * 2**30


def run_batch(project, lanes):
    lock = (project / "batch.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (project / "progress.json").exists():
        raise FileExistsError("Batch state already exists; inspect it before launching another supervisor")
    manifest = json.loads((project / "manifest.json").read_text())
    jobs, active = jobs_for(manifest), {}
    started = time.time()
    def stopped(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")
    signal.signal(signal.SIGTERM, stopped)
    try:
        while any(job["status"] == "pending" for job in jobs) or active:
            for name, (process, stream, job, deadline) in list(active.items()):
                code = process.poll()
                if code is None and time.monotonic() > deadline:
                    os.killpg(process.pid, signal.SIGTERM)
                    job["status"] = "timeout"
                    try:
                        code = process.wait(timeout=120)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        code = process.wait()
                if code is not None:
                    stream.close()
                    job.update(status=job["status"] if job["status"] == "timeout" else ("finished" if code == 0 else "error"),
                               exit_code=code, finished_at=time.time())
                    del active[name]
                    print(json.dumps({"job": name, "status": job["status"], "exit_code": code}), flush=True)
                    make_report(project, jobs)
            for job in jobs:
                if len(active) >= lanes or not available(project):
                    break
                if job["status"] != "pending":
                    continue
                directory = project / "runs" / job["name"]
                directory.mkdir(exist_ok=False)
                stream = (directory / "driver.log").open("w")
                command = [sys.executable, "-u", "-m", "experiments.contention_trial", "--project", str(project),
                           "--pair", job["pair"], "--harness", job["harness"], "--mode", job["mode"],
                           "--out", str(directory), "--timeout", str(manifest["agent_timeout_s"])]
                process = subprocess.Popen(command, cwd=project / "CoDesk", stdout=stream,
                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
                job.update(status="running", pid=process.pid, started_at=time.time())
                cap = manifest["agent_timeout_s"] * (2 if job["mode"] == "sequential" else 1) + 1800
                active[job["name"]] = (process, stream, job, time.monotonic() + cap)
                print(json.dumps({"job": job["name"], "status": "running", "pid": process.pid}), flush=True)
            save(project / "progress.json", {"started_at": started, "updated_at": time.time(),
                 "active": list(active), "finished": sum(j["status"] in ("finished", "error", "timeout") for j in jobs),
                 "total": len(jobs), "jobs": jobs, "admission_available": available(project)})
            if active or any(j["status"] == "pending" for j in jobs):
                time.sleep(5)
    finally:
        for process, stream, job, deadline in active.values():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
            stream.close()
        report = make_report(project, jobs)
        save(project / "progress.json", {"started_at": started, "updated_at": time.time(),
             "active": list(active), "finished": report["finished"], "total": len(jobs), "jobs": jobs})
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "report"])
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--lanes", type=int, default=2)
    args = parser.parse_args(argv)
    project = args.project.resolve()
    if args.command == "report":
        jobs = json.loads((project / "progress.json").read_text())["jobs"]
        print(json.dumps(make_report(project, jobs)["conditions"]))
        return 0
    if args.lanes not in (1, 2):
        raise ValueError("This shared-host experiment permits one or two desktop VMs")
    return run_batch(project, args.lanes)


if __name__ == "__main__":
    raise SystemExit(main())
