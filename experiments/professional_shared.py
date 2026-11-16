"""Run two independent GUI agents on one professional application and document."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import html
import json
from pathlib import Path
import shutil
import threading
import time

from experiments import professional_trajectories as collector
from experiments.summarize_professional_trajectories import summarize


class Timeline:
    def __init__(self, root):
        self.root = root
        self.lock = threading.Lock()
        self.sequence = 0
        self.action_sequence = 0
        self.mutations = Counter()
        self.inflight = {}
        self.observations = {}
        self.model_observations = {}

    def _write(self, kind, task, data):
        self.sequence += 1
        record = dict(data, event=kind, task=task, sequence=self.sequence, recorded_at=time.time())
        collector.append(self.root / "timeline.jsonl", record)
        return record

    def observation_start(self, task):
        with self.lock:
            return {"started_at": time.time(), "mutations": dict(self.mutations),
                    "inflight": dict(self.inflight), "sequence": self.sequence}

    def observation_end(self, task, observation, path, window):
        with self.lock:
            data = dict(observation, finished_at=time.time(), screenshot=path, window=window)
            self.observations[task] = data
            self._write("observation", task, data)

    def record(self, task, kind, event):
        with self.lock:
            if kind == "model_request":
                self.model_observations[task] = dict(self.observations[task])
                event["observation"] = self.model_observations[task]
            elif kind == "action_start":
                self.action_sequence += 1
                observation = self.model_observations[task]
                event.update(global_action_id=self.action_sequence,
                    model_observation=observation["screenshot"],
                    observation_age_s=round(time.time() - observation["finished_at"], 3),
                    foreign_mutations_since_observation=sum(count - observation["mutations"].get(actor, 0)
                        for actor, count in self.mutations.items() if actor != task),
                    foreign_input_inflight=any(actor != task for actor in self.inflight.values()),
                    foreign_input_at_observation=any(actor != task for actor in observation["inflight"].values()),
                    input_started_at=time.time())
                if event["action"]["type"] not in ("screenshot", "wait"):
                    self.mutations[task] += 1
                    self.inflight[event["global_action_id"]] = task
            elif kind == "input_end":
                event["input_finished_at"] = time.time()
                self.inflight.pop(event["global_action_id"], None)
            self._write(kind, task, event)


class AgentDesktop:
    def __init__(self, desktop, task, timeline):
        self.desktop = desktop
        self.name = desktop.name
        self.task = task
        self.timeline = timeline

    def raw(self, argv, **kwargs):
        return self.desktop.raw(argv, **kwargs)

    def focus(self):
        return self.desktop.focus()

    def screenshot(self, path):
        observation = self.timeline.observation_start(self.task)
        script = ("import subprocess,sys,tempfile; from pathlib import Path; from PIL import Image; "
                  "temporary=tempfile.TemporaryDirectory(prefix='paragui-shot-'); "
                  "path=str(Path(temporary.name)/'screen.png'); "
                  "subprocess.run(['scrot','--overwrite',path],check=True); "
                  "Image.open(path).convert('RGB').resize((1280,800),Image.Resampling.LANCZOS)"
                  ".save(sys.stdout.buffer,format='PNG'); temporary.cleanup()")
        Path(path).write_bytes(self.raw(["python3", "-c", script]).stdout)
        self.timeline.observation_end(self.task, observation,
            str(Path(path).relative_to(self.timeline.root)), self.focus())


def overlap_seconds(intervals):
    boundaries = []
    for actor, start, end in intervals:
        if end > start:
            boundaries.extend([(start, actor, 1), (end, actor, -1)])
    active, previous, overlap = Counter(), None, 0.0
    for timestamp, actor, delta in sorted(boundaries):
        if previous is not None and sum(count > 0 for count in active.values()) > 1:
            overlap += timestamp - previous
        active[actor] += delta
        previous = timestamp
    return round(overlap, 3)


def verify_timeline(root, records, results):
    errors = []
    if [record["sequence"] for record in records] != list(range(1, len(records) + 1)):
        errors.append("Timeline event sequence is not contiguous")
    phases = {}
    for kind in ("action_start", "input_end", "action_end"):
        selected = [record for record in records if record["event"] == kind]
        phases[kind] = {record["global_action_id"]: record for record in selected}
        if len(phases[kind]) != len(selected):
            errors.append("Duplicate global action ID in " + kind)
    if not (phases["action_start"].keys() == phases["input_end"].keys() == phases["action_end"].keys()):
        errors.append("Some global actions lack start, input-end or completion records")
    for identifier, end in phases["action_end"].items():
        for kind in ("action_start", "input_end"):
            other = phases[kind].get(identifier, {})
            if any(other.get(key) != end.get(key) for key in ("task", "step", "turn", "call_id", "action")):
                errors.append(f"Action identity changed across timeline phases: {identifier}")
    final_hashes = collector.hashes(root / "shared/workspace")
    for result in results:
        task = result["task"]
        path = root / task / "actions.jsonl"
        actions = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        completed = [record for record in records if record["event"] == "action_end" and record["task"] == task]
        if len(actions) != len(completed) or len(actions) != result["actions"]:
            errors.append("Action count differs between timeline, agent log and result: " + task)
        for action, complete in zip(actions, completed):
            if any(complete.get(key) != value for key, value in action.items()):
                errors.append("Agent action differs from global timeline: " + task)
        if result.get("output_hashes") != final_hashes:
            errors.append("Result does not describe the common final workspace: " + task)
        if result.get("pending_shared_evaluation") or result.get("frozen_at", 0) < result["finished_at"]:
            errors.append("Workspace was not frozen after agent completion: " + task)
    return errors


def analyze(root, results):
    records = [json.loads(line) for line in (root / "timeline.jsonl").read_text().splitlines()]
    actions = [record for record in records if record["event"] == "action_end"]
    starts = [record for record in records if record["event"] == "action_start"]
    inputs = [record for record in records if record["event"] == "input_end"
              and record["action"]["type"] not in ("screenshot", "wait")]
    request_intervals, request_errors = [], Counter()
    for result in results:
        request_path = root / result["task"] / "requests.jsonl"
        requests = [json.loads(line) for line in request_path.read_text().splitlines()] if request_path.exists() else []
        for request in requests:
            request_intervals.append((result["task"], request["started_at"],
                                      request["started_at"] + request["latency_s"]))
            if not request.get("ok"):
                request_errors[str(request.get("http_status", request.get("error_type")))] += 1
    actor_intervals = [(result["task"], result["agent_started_at"], result["finished_at"])
                       for result in results if "agent_started_at" in result]
    counts = Counter(record["task"] for record in actions)
    summary = {
        "shared_container": len({result.get("container") for result in results}) == 1
            and all(result.get("container") for result in results),
        "agent_lifetime_overlap_s": overlap_seconds(actor_intervals),
        "model_http_overlap_s": overlap_seconds(request_intervals),
        "input_dispatch_overlap_s": overlap_seconds([(record["task"], record["input_started_at"],
            record["input_finished_at"]) for record in inputs]),
        "action_start_actor_switches": sum(left["task"] != right["task"] for left, right in zip(starts, starts[1:])),
        "actions_by_agent": dict(counts), "completed_actions": len(actions),
        "actions_by_type": {result["task"]: dict(Counter(record["action"]["type"] for record in actions
            if record["task"] == result["task"])) for result in results},
        "potentially_stale_actions": sum(bool(record["foreign_mutations_since_observation"]
            or record["foreign_input_at_observation"] or record["foreign_input_inflight"]) for record in starts),
        "potentially_stale_input_actions": sum(record["action"]["type"] not in ("screenshot", "wait")
            and bool(record["foreign_mutations_since_observation"] or record["foreign_input_at_observation"]
                     or record["foreign_input_inflight"]) for record in starts),
        "action_errors": sum(record["status"] != "ok" for record in actions),
        "request_errors": dict(request_errors),
        "unmatched_action_starts": len(starts) - len(actions),
        "timeline_sequence_contiguous": [record["sequence"] for record in records] == list(range(1, len(records) + 1)),
        "integrity_errors": verify_timeline(root, records, results),
    }
    summary["parallel_activity_observed"] = bool(summary["shared_container"]
        and summary["agent_lifetime_overlap_s"] > 0 and summary["model_http_overlap_s"] > 0
        and len(counts) == len(results) and summary["action_start_actor_switches"] > 0)
    summary["definitions"] = {
        "potentially_stale_actions": "Other-agent input started after the model observation began, or was in flight at observation/action time; not proof of harmful UI change.",
        "input_dispatch_overlap_s": "Overlap of host-issued input command intervals, excluding settling and screenshot time; not measured X-server event timestamps.",
        "parallel_activity_observed": "Same container, overlapping agent lifetimes and HTTP requests, both agents acted, and action-start order switched agents.",
        "focus": "Both agents share one application; window title changes alone cannot establish focus theft or ownership.",
    }
    collector.save(root / "concurrency.json", summary)
    return summary, actions


def render_report(root, manifest, results, dataset=None):
    integrity = summarize(root, Path(dataset or manifest["dataset"]))
    metrics, actions = analyze(root, results)
    integrity["integrity_errors"].extend(metrics["integrity_errors"])
    integrity["integrity_passed"] = not integrity["integrity_errors"]
    collector.save(root / "trajectory-summary.json", integrity)
    lines = ["# 专业软件共享桌面实验", "",
        f"条件：**{manifest['mode']}**；任务：**{' + '.join(manifest['tasks'])}**；模型：`{manifest['model']}`。", "",
        "两个独立上下文只收到自己的任务，操作同一个 Docker/X11 桌面、同一个应用实例和原生项目。"
        "没有键鼠/批次互斥、自动抢回窗口或通信工具；日志锁仅保护记录。GUI-only 是工具表面和提示约束。",
        "", "所有 agent 停止后关闭应用，再对共同最终文件统一评分；不会在另一方仍工作时启动评分器。",
        "", "| 任务 | 停止原因 | 原始评分 | 动作 | 响应 |", "|---|---|---:|---:|---:|"]
    for result in results:
        score = result.get("score")
        lines.append(f"| {result['task']} | {result['status']} | {score if score is not None else '未评分'} | {result['actions']} | {result['model_responses']} |")
    lines += ["", "## 并发证据", "",
        f"- 同一容器：{metrics['shared_container']}；观测到并行活动：{metrics['parallel_activity_observed']}。",
        f"- agent 存活重叠：{metrics['agent_lifetime_overlap_s']} 秒；HTTP 请求重叠：{metrics['model_http_overlap_s']} 秒。",
        f"- 输入命令派发区间重叠：{metrics['input_dispatch_overlap_s']} 秒；动作起始序列换手：{metrics['action_start_actor_switches']} 次。",
        f"- 可能基于过期画面的动作：{metrics['potentially_stale_actions']}；动作错误：{metrics['action_errors']}。",
        f"- 其中实际键鼠输入暴露：{metrics['potentially_stale_input_actions']}；等待/截图不计入这一项。",
        f"- 请求错误：`{json.dumps(metrics['request_errors'])}`；完整性检查：{integrity['integrity_passed']}。",
        "", "## 文件", "",
        "- [交错回放](index.html)、[并发统计](concurrency.json)、[全局事件流](timeline.jsonl)。",
        "- 每个任务目录有独立请求、响应、动作、截图与 trajectory.html；workspace 是共同最终文件的快照。",
        "- shared/workspace 为真实共享目录；shared/evaluation 为统一评分副本。", "",
        "## 解释边界", "",
        "- 这是单次探索，不足以估计成功率或归因性能变化。completed 仅代表模型停止。",
        "- 已有 solo 仅包含 A 任务，且提示、运行时段不同；不能当成严格匹配的 A+B 对照。",
        "- sequential 使用同一入口、初始输入与提示，但按 A→B 执行，可用于后续匹配对照。",
        "- 画面过期指标仅计其他 agent 输入的暴露，不断言每次都造成损害；派发重叠不是实际 X11 事件重叠。",
        "- 原始六项评分器保持不变，需结合截图复核；无 Codex CLI、无 YOLO、无代码控制台工具。",
    ]
    (root / "REPORT.md").write_text("\n".join(lines) + "\n")
    frames = [{"task": record["task"], "step": record["step"], "action": record["action"],
               "window_before": record["window_before"], "status": record["status"],
               "foreign_mutations_since_observation": record["foreign_mutations_since_observation"],
               "recorded_at": record["recorded_at"],
               "screenshot": record["task"] + "/" + record["screenshot_after"]} for record in actions]
    frame_json = json.dumps(frames, ensure_ascii=False).replace("<", "\\u003c")
    links = " · ".join(f'<a href="{html.escape(task)}/trajectory.html">{html.escape(task)}</a>' for task in manifest["tasks"])
    if (root / "REVIEW.md").exists():
        links += ' · <a href="REVIEW.md">Incident and grading review</a>'
    page = '''<!doctype html><meta charset="utf-8"><title>paraGUI shared desktop</title>
<style>body{font:16px system-ui;max-width:1320px;margin:24px auto;background:#15202b;color:#eee}a{color:#8dd7ff}img{width:100%}input{width:65%}pre{white-space:pre-wrap}</style>
<h1>paraGUI: ''' + html.escape(manifest["mode"]) + '''</h1><a href="REPORT.md">Report</a> · ''' + links + '''
<p>Global completion order; overlapping input may be visible in either agent's screenshot.</p>
<button id="prev">Previous</button><input id="step" type="range" min="0" value="0"><button id="next">Next</button><span id="count"></span>
<pre id="caption"></pre><img id="screen"><script>const frames=''' + frame_json + ''';
const slider=document.getElementById('step');slider.max=Math.max(0,frames.length-1);
function show(){const frame=frames[+slider.value];document.getElementById('count').textContent=(frames.length?+slider.value+1:0)+'/'+frames.length;
document.getElementById('caption').textContent=JSON.stringify(frame||{},null,2);if(frame)document.getElementById('screen').src=frame.screenshot;}
slider.oninput=show;document.getElementById('prev').onclick=()=>{slider.value=Math.max(0,+slider.value-1);show()};
document.getElementById('next').onclick=()=>{slider.value=Math.min(frames.length-1,+slider.value+1);show()};show();</script>'''
    (root / "index.html").write_text(page)
    return integrity, metrics


def run(args, config):
    args.dataset, args.out = args.dataset.resolve(), args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    tasks = [args.pair + side for side in "ab"]
    shared = args.out / "shared"
    shared.mkdir()
    shutil.copytree(args.dataset / "dataset/pairs" / args.pair / "inputs", shared / "workspace")
    desktop = collector.Desktop(shared, args.pair, args.image)
    timeline = Timeline(args.out)
    source_files = {"collector.py": Path(__file__), "collector_support.py": Path(collector.__file__)}
    for name, source in source_files.items():
        shutil.copy2(source, args.out / name)
    manifest = {"schema_version": 1, "tasks": tasks, "mode": args.mode, "dataset": str(args.dataset),
        "model": config["model"], "reasoning_effort": config.get("reasoning_effort", "high"),
        "access": args.access, "reference_exposed": False, "yolo_enabled": False, "codex_cli": False,
        "desktop_count": 1, "application_instances": 1, "shared_workspace": True,
        "input_mediation": "none; no input or batch lock", "agent_task_visibility": "own instruction only",
        "source_hashes": {name: hashlib.sha256(source.read_bytes()).hexdigest() for name, source in source_files.items()},
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "image": collector.command(["docker", "image", "inspect", args.image, "--format", "{{.Id}}"], text=True).stdout.strip(),
        "max_actions_per_agent": args.max_actions, "max_turns_per_agent": args.max_turns,
        "timeout_per_agent_s": args.timeout, "started_at": time.time(), "status": "starting"}
    collector.save(args.out / "manifest.json", manifest)
    results = []
    try:
        desktop.start()
        manifest.update(container=desktop.name, status="running")
        collector.save(args.out / "manifest.json", manifest)
        barrier = threading.Barrier(len(tasks)) if args.mode == "parallel" else None
        def execute(task):
            adapter = AgentDesktop(desktop, task, timeline)
            try:
                return collector.trial(args, task, config, desktop=adapter, barrier=barrier,
                    observe=lambda kind, event: timeline.record(task, kind, event))
            except BaseException:
                if barrier is not None:
                    barrier.abort()
                raise
        if args.mode == "parallel":
            with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                futures = [executor.submit(execute, task) for task in tasks]
                results = [future.result() for future in futures]
        else:
            results = [execute(task) for task in tasks]
    except Exception as error:
        manifest.update(status="error", error_type=type(error).__name__)
        raise
    finally:
        desktop.stop()
        manifest["desktop_stopped_at"] = time.time()
        collector.save(args.out / "manifest.json", manifest)
    try:
        scores = collector.evaluate(shared, args.pair, args.dataset, args.image)
    except Exception as error:
        scores = None
        manifest["evaluation_error"] = type(error).__name__
    final_hashes = collector.hashes(shared / "workspace")
    for result in results:
        root = args.out / result["task"]
        shutil.rmtree(root / "workspace")
        shutil.copytree(shared / "workspace", root / "workspace")
        result.update(output_hashes=final_hashes, pending_shared_evaluation=False,
            evaluation_scope="common final state after all agents stopped",
            evaluation_directory="../shared/evaluation", frozen_at=manifest["desktop_stopped_at"])
        if scores is not None:
            result.update(evaluation=scores, score=scores[result["task"][-1]]["score"])
        else:
            result["evaluation_error"] = manifest["evaluation_error"]
        collector.save(root / "result.json", result)
    manifest.update(status="finished", finished_at=time.time(), output_hashes=final_hashes)
    collector.save(args.out / "manifest.json", manifest)
    collector.save(args.out / "summary.json", results)
    integrity, metrics = render_report(args.out, manifest, results)
    print(json.dumps({"out": str(args.out), "results": [{key: result.get(key) for key in
        ("task", "status", "score", "actions", "model_responses")} for result in results],
        "integrity_passed": integrity["integrity_passed"], "concurrency": metrics}, ensure_ascii=False), flush=True)
    return int(not integrity["integrity_passed"] or bool(manifest.get("evaluation_error"))
        or any(result["status"] == "error" for result in results))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pair", choices=sorted(collector.APPS), default="p3")
    parser.add_argument("--mode", choices=["parallel", "sequential"], default="parallel")
    parser.add_argument("--image", default="paragui/professional-authoring:20261030")
    parser.add_argument("--access", choices=["gui"], default="gui")
    parser.add_argument("--max-actions", type=int, default=300)
    parser.add_argument("--max-turns", type=int, default=90)
    parser.add_argument("--timeout", type=int, default=1500)
    args = parser.parse_args(argv)
    if min(args.max_actions, args.max_turns, args.timeout) <= 0:
        parser.error("Budgets must be positive")
    return run(args, json.loads(args.credentials.read_text()))


if __name__ == "__main__":
    raise SystemExit(main())
