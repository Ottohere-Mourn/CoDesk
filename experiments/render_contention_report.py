"""Render the completed paired comparison; preserve all original scores."""
import argparse
import json
from pathlib import Path


def render(project):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    summary = json.loads((project / "summary.json").read_text())
    manifest = json.loads((project / "manifest.json").read_text())
    if summary["valid_conditions"] != summary["planned"]:
        raise ValueError("The complete report requires a valid result for every condition")
    order = ["codex_sequential", "codex_parallel", "freehand_sequential", "freehand_parallel"]
    matrix = np.array([[case["conditions"][key]["mean_score"] for key in order]
                       for case in summary["cases"]])
    labels = [case["pair"].replace("_", " ") for case in summary["cases"]]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    plot = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(4), ["Codex\nSequential", "Codex\nParallel", "Freehand\nSequential", "Freehand\nParallel"])
    ax.set_yticks(range(len(labels)), labels)
    ax.xaxis.tick_top()
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            value = matrix[row, column]
            ax.text(column, row, f"{value:.2f}", ha="center", va="center",
                    color="white" if value >= 0.75 else "black", fontsize=11)
    ax.set_title("Original OSWorld task pairs · GPT-6 Astra", pad=48, fontsize=15)
    fig.colorbar(plot, ax=ax, label="Mean original evaluator score (two tasks)", shrink=0.8)
    fig.text(0.02, 0.015, "One run per condition. WeeklySales includes an evaluator worksheet-name constraint; see report.", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(project / "comparison.png", dpi=180)
    fig.savefig(project / "comparison.svg")
    plt.close(fig)

    rows = []
    for harness in ["codex", "freehand"]:
        seq = summary["conditions"][harness + "_sequential"]
        par = summary["conditions"][harness + "_parallel"]
        rows.append(f"| {harness} | {seq['joint_passes']}/10 | {par['joint_passes']}/10 | "
                    f"{seq['mean_score']:.3f} | {par['mean_score']:.3f} | "
                    f"{seq['mean_score'] - par['mean_score']:.3f} |")
    recovery = json.loads((project / "recovery_progress.json").read_text())
    records = list(summary["records"].values())
    usage = {key: sum((r.get("usage") or {}).get(key) or 0 for r in records)
             for key in ["input_tokens", "output_tokens", "total_tokens"]}
    requests = sum(r["model_requests"] for r in records)
    errors = sum(r["api_errors"] for r in records)
    lines = ["# OSWorld 原版竞争场景：Codex 与 Freehand", "",
        f"10 组任务的 40 个条件已取得有效配对评分；完成 {len(recovery['attempts'])} 次基础设施补跑，原始失败记录保留。",
        "两种 harness 均使用 gpt-6-astra、high、同一 API 和相同 Guest 配置，每个 agent 限时 1800 秒。", "",
        "| Harness | 顺序双通过 | 并发双通过 | 顺序平均分 | 并发平均分 | 平均分下降 |",
        "|---|---:|---:|---:|---:|---:|", *rows, "",
        "平均分使用两项原版评分的均值；双通过要求两项均为 1.0。每个条件仅运行一次，这些数字描述本轮样本。", "",
        "![逐组原版评分](comparison.png)", "",
        "## 已复核的干扰", "",
        "- Freehand / 销售增长图表与汇总：Sheet2 创建并完成后，图表会话显式删除 Sheet2；顺序 1/1，并发 1/0。",
        "- Codex / 网页书签与文件夹：网页书签已正确出现在书签栏，文件夹会话随后清理该书签 ID；顺序 1/1，并发 0/1。",
        "- Freehand / 换行与自动保存：自动保存延迟 500 被另一会话的界面输入改成 50，随后自动保存配置键被删除；顺序 1/1，并发 1/0。", "",
        "共同现象是共享界面或文件状态发生变化后，一个会话的修正、清理动作破坏了另一个会话的成果。具体工具调用和版本记录见 [案例证据](RACE_CASES.md)。", "",
        "## 原版评分约束", "",
        "WeeklySales 图表任务只要求新工作表，评分器固定查找 Sheet2。两个顺序输出把正确的图表放在 Sales & COGS 工作表，原版评分为 0。对独立副本仅改工作表名后，原版评分器返回 1。正式统计保留原始的 0；这个现象不能作为并发损失证据。",
        "诊断原件见 [独立改名实验](diagnostics/weekly-chart-sheet-name/diagnosis.json)。", "",
        "## 方法与执行记录", "",
        "每轮使用全新的 OSWorld 桌面；并发时两个 agent 共享一台 Guest，顺序时同样预置两个任务，再按 A→B 执行。每个 agent 只收到自己的原版指令。任务内容和官方评分器未修改。",
        "两种 harness 均可在 Guest 内使用 Bash、文件、脚本与 GUI。Codex 为官方 CLI 0.163.0，保留原生工具和上下文管理；Freehand 保留 mini-harness 的原生循环与最近 4 张图片窗口。模型、推理档位和时间预算相同。",
        "Guest 为 4 vCPU、8 GiB RAM，Docker 内存上限 10 GiB；主队列最多两台 Guest。顺序对照固定 A→B，没有反向顺序或多次重复。",
        "被记录并补跑的基础设施中断包括运行包上传和 Guest 控制连接错误。运行包上传时限及只读文件/状态请求的有限重试在宿主适配层修复，未重放 GUI 动作；修订记录见 revisions/。原始评分文件保持原样，通过 effective_attempts.json 指向补跑结果。",
        "测试记录包含开跑前的 49 项测试，以及后续基础设施修复的针对性回归测试。", "",
        f"有效条件合计 {requests} 次模型请求，记录到 {errors} 次上游错误（与 agent/评分器错误分别记录）。已返回的用量合计 {usage['input_tokens']:,} 输入、{usage['output_tokens']:,} 输出 tokens；输入包括重复与缓存上下文，不代表独立文本量。", "",
        "[完整汇总](summary.json) · [CSV](scores.csv) · [任务和源码清单](manifest.json) · [补跑映射](effective_attempts.json) · [补跑记录](recovery_progress.json)",
        "", "原始结果和完整轨迹保存在 runs/ 与 recoveries/。模型声称完成与官方评分是两个独立结果。",
        "Codex 配置核对依据：[OpenAI 官方配置参考](https://developers.openai.com/codex/config-reference/)。"]
    (project / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"valid_conditions": summary["valid_conditions"], "conditions": summary["conditions"],
                      "effective_usage": usage, "final_report": str(project / "FINAL_REPORT.md")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    render(parser.parse_args().project.resolve())
