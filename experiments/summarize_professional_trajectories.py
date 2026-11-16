"""Build a portable report and check the integrity of recorded desktop trials."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import html
import json
from pathlib import Path

from PIL import Image


def valid_png(path):
    try:
        with Image.open(path) as image:
            image.verify()
            return image.format == "PNG"
    except (OSError, ValueError, SyntaxError):
        return False


def summarize(root: Path, dataset: Path | None = None):
    rows, errors = [], []
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        for task in manifest.get("tasks", []):
            if not (root / task / "result.json").is_file():
                errors.append(f"Missing trial result: {task}")
        collector = root / "collector.py"
        if manifest.get("runner_sha256") and (not collector.is_file() or
                hashlib.sha256(collector.read_bytes()).hexdigest() != manifest["runner_sha256"]):
            errors.append("Collector hash does not match manifest.json")
        for name, expected in manifest.get("source_hashes", {}).items():
            source = root / name
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                errors.append("Collector source hash mismatch: " + name)
    for path in sorted(root.glob("*/result.json")):
        folder = path.parent
        result = json.loads(path.read_text())
        actions = [json.loads(line) for line in (folder / "actions.jsonl").read_text().splitlines()] if (folder / "actions.jsonl").exists() else []
        requests = [json.loads(line) for line in (folder / "requests.jsonl").read_text().splitlines()] if (folder / "requests.jsonl").exists() else []
        issues = []
        if result["actions"] != len(actions):
            issues.append("Action count does not match result.json")
        if [a["step"] for a in actions] != list(range(1, len(actions)+1)):
            issues.append("Action numbering is not contiguous")
        screenshots = [folder / "screenshots/0000.png"] + [folder / a["screenshot_after"] for a in actions]
        missing = [str(p.relative_to(folder)) for p in screenshots if not valid_png(p)]
        if missing:
            issues.append("Missing/invalid screenshots: " + ", ".join(missing))
        responses = {int(p.stem): json.loads(p.read_text()) for p in (folder / "responses").glob("*.json") if p.stem.isdigit()}
        if len(responses) != result["model_responses"]:
            issues.append("Model response count does not match result.json")
        if (folder / "requests.jsonl").exists() and sum(bool(r.get("ok")) for r in requests) != len(responses):
            issues.append("Successful request count does not match model responses")
        batches = defaultdict(list)
        for action in actions:
            batches[action["turn"], action["call_id"]].append(action)
        for (turn, call_id), batch in batches.items():
            calls = [i for i in responses.get(turn, {}).get("output", [])
                     if i.get("type") == "function_call" and i.get("call_id") == call_id]
            # Errors or budgets can stop a batch; executed actions must be its exact prefix.
            expected = json.loads(calls[0]["arguments"]).get("actions", []) if len(calls) == 1 else []
            if [a["action"] for a in batch] != expected[:len(batch)]:
                issues.append(f"Action batch starting at {batch[0]['step']} is not grounded in its model response order")
        if dataset is not None:
            inputs = dataset / "dataset" / "pairs" / result["task"][:2] / "inputs"
            input_hashes = {str(p.relative_to(inputs)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(inputs.rglob("*")) if p.is_file()}
            if not input_hashes or input_hashes != result.get("input_hashes"):
                issues.append("Input hashes do not match the source dataset")
        for name, expected in result.get("output_hashes", {}).items():
            p = folder / "workspace" / name
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
                issues.append("Output hash mismatch: " + name)
        side = result["task"][-1]
        checks = result.get("evaluation", {}).get(side, {}).get("checks", {})
        failed = [name for name, check in checks.items() if not check["passed"]]
        row = {k: result.get(k) for k in ("task", "software", "model", "reasoning_effort", "status", "score", "actions", "model_responses", "wall_s", "usage", "agent_summary", "agent_claimed_complete")}
        row.update(screenshots=len(screenshots)-len(missing), api_errors=sum(not r.get("ok") for r in requests),
                   action_errors=sum(a["status"] != "ok" for a in actions), failed_checks=failed,
                   integrity_errors=issues)
        rows.append(row)
        errors.extend(folder.name + ": " + issue for issue in issues)
    summary = {"trials": rows, "integrity_passed": not errors, "integrity_errors": errors,
               "input_hashes_checked": dataset is not None,
               "total_actions": sum(r["actions"] for r in rows),
               "total_screenshots": sum(r["screenshots"] for r in rows),
               "total_model_responses": sum(r["model_responses"] for r in rows)}
    (root / "trajectory-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    models = ", ".join(sorted({f"{r['model']} / {r['reasoning_effort']}" for r in rows}))
    lines = ["# 专业软件 agent 操作轨迹", "", "这是模型实际操作桌面得到的独立试跑；各任务从原始输入启动。模型只收到自己的任务与截图，通过鼠标、键盘工具执行。没有向模型提供参考答案、评分器或文件读取工具。", "",
             f"模型：`{models}`（以各任务 result.json 为准）。采集器是 Responses API 循环，未运行 Codex CLI，未开启 YOLO。", "",
             "| 任务 | 软件 | 运行状态 | 评分 | 动作数 | 模型响应 | 回放 |", "|---|---|---|---:|---:|---:|---|"]
    for row in rows:
        task = row["task"]
        score = f"{row['score']:.3f}" if row["score"] is not None else "未评分"
        lines.append(f"| {task} | {row['software']} | {row['status']} | {score} | {row['actions']} | {row['model_responses']} | [打开]({task}/trajectory.html) |")
    lines.extend(["", f"合计 {summary['total_actions']} 个动作、{summary['total_screenshots']} 张截图、{summary['total_model_responses']} 次模型响应。轨迹完整性检查：{'通过' if not errors else '未通过'}。", "",
        "`completed` 表示模型结束作答，不代表通过评分；`max_actions`、`max_turns`、`timeout` 保留真实中间产物。评分读取停止后的工作目录副本，逐项结果见各任务 `evaluation/scores.json`。", "",
        "## 未通过的检查", ""])
    for row in rows:
        lines.append(f"- **{row['task']}**：" + (", ".join(row["failed_checks"]) or "所有已有检查均通过") + "。")
    lines.extend(["", "## 文件", "", "- `*/trajectory.html`：可直接打开的逐步截图回放。",
        "- `*/actions.jsonl`：逐步操作、前后焦点、截图路径、时间及错误状态。",
        "- `*/requests/*.json`：实际请求，图像使用相对路径；`*/responses/*.json`：模型返回的原始响应。请求不含 API 凭据。",
        "- `*/instruction.txt`、`*/prompt.json`：任务原文、操作规则与工具定义。",
        "- `*/workspace/`：模型操作结束时的文件；`*/evaluation/`：独立检查的副本、原生状态及评分。",
        "- `*/result.json`：停止原因、模型自述、用量、输入/输出哈希、独立评分。",
        "", "## 解释边界", "", "- 当前是 solo 试跑，不能据此判断多个 agent 共享桌面的干扰。",
        "- `gui` 模式没有 shell 工具；禁止代码控制台是提示约束，需要结合动作与截图检查。应用正常表达式字段允许使用。",
        "- 动作批次中的每个操作都有截图，但模型仅收到批次最后一张；请求保留最近 3 张图和全部文字/工具历史。",
        "- 沿用原批次 6 项等权评分，不等同全面视觉或工程验收。例如 FreeCAD SVG 检查要求四个 `<circle>` 标签，其他正确的 SVG 表达可能失分；QGIS 分类检查要求类别完全相等。",
        "- 采集器没有自动重放失败操作；模型调用重试单独记录。完整性检查涵盖产物哈希、截图、响应数量及每批动作与模型返回的顺序对应。",
        "- 原始输入哈希：" + ("已与数据集逐项比较。" if dataset is not None else "未比较；使用 --dataset 指定原始数据包后可检查。"), ""])
    (root / "REPORT.md").write_text("\n".join(lines))
    cards = "".join('<li><a href="' + r["task"] + '/trajectory.html">' + html.escape(r["software"] + " / " + r["task"]) + "</a> — " + str(r["actions"]) + " actions, score " + str(r["score"]) + "</li>" for r in rows)
    (root / "index.html").write_text('<!doctype html><meta charset="utf-8"><title>paraGUI trajectories</title><style>body{font:18px system-ui;max-width:900px;margin:60px auto;line-height:2}a{color:#146d91}</style><h1>Professional GUI trajectories</h1><p>Real model actions, screenshots and independently graded artifacts.</p><ul>' + cards + '</ul><a href="REPORT.md">Report</a> · <a href="trajectory-summary.json">Summary JSON</a>')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--dataset", type=Path, help="Original authoring package containing dataset/pairs; enables input hash checks")
    args = parser.parse_args()
    summary = summarize(args.root, args.dataset)
    print(json.dumps({k: v for k, v in summary.items() if k != "trials"}, ensure_ascii=False))
    return int(not summary["integrity_passed"])


if __name__ == "__main__":
    raise SystemExit(main())
