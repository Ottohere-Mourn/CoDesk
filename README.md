# CoDesk / ParaGUI — Selected 23 High-Quality Multi-Agent Desktop (GUI + CLI) Cases

本分支（`codex/selected-23-cases`）是 **纯粹只保留 23 道入选高质量双智能体（`GUI + CLI` 混合）基准任务与全量 184 条实测轨迹** 的精选独立分支，统一执行 **严格全对判分标准（`pass_threshold = 1.0`，任意子检查项失败即判 `joint_pass = False`）**，并已完成全部扣分项的人工/代码复核修正。

- **中文总览与逐题成绩表**：[`docs/CURATED_23CASES_AND_TRAJECTORIES_20261125_ZH.md`](docs/CURATED_23CASES_AND_TRAJECTORIES_20261125_ZH.md)
- **机器可读 23 题主清单**：[`lists/curated_23cases_and_trajectories_20261125.json`](lists/curated_23cases_and_trajectories_20261125.json)
- **统一 Python 注册表**：[`tasks/curated_23cases_v1/registry.py`](tasks/curated_23cases_v1/registry.py)（`SELECTED_23_IDS` 共 23 题）
- **92 局 / 184 角色完整双模轨迹**：[`trajectories/curated_23cases_20261125/`](trajectories/curated_23cases_20261125/README.md)
- **造题与审计 Skills**：[`.agents/skills/paragui-case-design/`](.agents/skills/paragui-case-design/SKILL.md)（盲并发共居）与 [`.agents/skills/paragui-collab-case-design/`](.agents/skills/paragui-collab-case-design/SKILL.md)（明示同伴双向协作）

## 入选 23 题组成与双模型（`effort = high`，严格 `pass_threshold = 1.0`）整体表现

| 子套件 | 题数 | 入选题号 | `gpt-6.1-sol` (`Isolated -> Shared`) | `gpt-6-astra` (`Isolated -> Shared`) | 执行器入口 |
|---|---:|---|---|---|---|
| `Curated-8` | 8 | `EC-01, EC-03, RBS-06, RBS2-06, RBS3-01, RBS3-02, RBS3-04, RBS3-05` | `0.8718 (62.5%) -> 0.8394 (62.5%)` | `1.0000 (100.0%) -> 0.9175 (62.5%)` | `experiments/curated_8cases_v1.py` |
| `AW-v1 (2h)` | 5 | `AW-12, AW-14, AW-15, AW-19, AW-20` | `1.0000 (100.0%) -> 0.9321 (60.0%)` | `0.9778 (80.0%) -> 0.9778 (80.0%)` | `experiments/authentic_workstation_v1.py` |
| `NF-v1` | 5 | `NF-01, NF-05, NF-11, NF-13, NF-14` | `0.9260 (60.0%) -> 0.8762 (20.0%)` | `0.9701 (60.0%) -> 0.9583 (80.0%)` | `experiments/novel_frontier_v1.py` |
| `NF2 (2h)` | 5 | `NF2-05, NF2-11, NF2-12, NF2-13, NF2-15` | `0.9891 (80.0%) -> 0.9458 (60.0%)` | `0.9274 (40.0%) -> 0.9131 (40.0%)` | `experiments/novel_frontier_v2.py` |
| **全量 23 题合计** | **23** | — | **`0.9370 (73.9%) -> 0.8907 (52.2%)`** | **`0.9729 (73.9%) -> 0.9385 (65.2%)`** | — |
| **15 题非饱和核心集** | **15** | 筛除 8 道双模 `1.0->1.0` 满平题 | **`0.9033 (60.0%) -> 0.8324 (26.7%)`** | **`0.9584 (60.0%) -> 0.9057 (46.7%)`** | — |

## 快速校验

```bash
PYTHONPATH=. pytest -q tests/
```
