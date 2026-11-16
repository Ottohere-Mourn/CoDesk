# 单个 WeaveBench seed → 同一 Writer 文档上的四角色冲突任务

## 原题与改动边界

- Seed：`DOC_task_2_heading_style_normalize`，原名“修 LibreOffice 15 个混合样式标题 (8 H1 + 2 H2 + 5 fake)”。
- 数据集：本地冻结的 `wanlilll/WeaveBench`，revision `ec498fc530b685d2fea5823a64a0f7538c8bbf6a`。
- 原题输入是一个含 15 个标题的 `report.odt`；原题要求找出 7 个错误标题、修为 Heading 1、生成目录并导出 PDF。
- 初始夹具只增加 `sec_01` 至 `sec_15` 的稳定书签；保留原始可见文字、标题顺序和全部 7 个样式错误。
- 这是 **WeaveBench-seeded 派生任务**，不是原封不动的官方任务，也不与官方 leaderboard 分数直接比较。
- 保留 hybrid GUI+CLI，包括 UNO/XML。去掉原题未对 agent 清楚公开的方法限制，验收条件全部公开。

## 四个角色不是四份文件

唯一权威对象：同一个桌面、同一个 Writer 会话、已经打开的 `/workspace/report.odt`。
共享窗口、样式表、文档内存、剪贴板、键鼠和文件系统；不额外提供输入锁或聊天工具。

| 角色 | 独立负责的修改 | 与其他角色的交互 |
|---|---|---|
| A 结构修复 | 检查并记录原始 7 个错误位置；15 个标题统一为真实 Heading 1 / outline 1 | 操作 B 正在改名/编号的同一批段落，必须保留 C 的样式 |
| B 标题和编号 | Results→Findings、Discussion→Interpretation、Author Bios→Contributors；原生章节编号 1–15 | 编号依赖 A 的 outline；改名立即使 D 的旧目录失效 |
| C 排版和正文 | Heading 1 的字体/字号/颜色、正文样式、A4 页边距、页码域；Limitations 后插入给定说明 | 共享样式和分页发生变化，D 的页码、目录缓存和 PDF 可能过期 |
| D 集成发布 | 一份原生目录；目录第 1 页、正文第 2 页；更新域，保存并导出 PDF、写版本回执 | 必须核实 A/B/C 的最终状态，不能用早期快照发布 |

四个 agent 一起启动，但 D 存在真实的上游依赖。D 可以提前准备目录，最后必须再核验。
“四个 agent 存活”不等于“四个 agent 一直同时写文档”；报告应同时展示实际动作重叠、等待和 token/耗时。

## 希望观察的故障

1. **丢失更新**：拿旧文件整体覆盖，导致已完成的标题、样式或正文修改消失。
2. **共享属性回退**：为了修复自己的标题/样式，顺带重置别人的编号或字号。
3. **过期派生内容**：标题/正文分页已变化，目录缓存或 PDF 仍来自旧状态。
4. **内存与磁盘分叉**：磁盘文件看似合格，但权威 Writer 窗口仍有未保存的不同版本。
5. **协调成本**：正确地加锁、等待、复查、刷新或重新导出，成功率未下降但消耗更多时间/token。

这些是需要实测的风险，不是预先认定必然发生。角色目标相容，不制造互相矛盾的最终要求。
允许 agent 自发使用共享文件协调和短临界区；可靠协调应得到满分，而不是被人为惩罚。

## 验收

公开契约和四份 prompt 位于 `tasks/weavebench_writer_conflict/`。

- A：书签/顺序、真实 Heading 1、原始错误审计。
- B：最终标题、原生章节编号定义、最终 1–15 编号。
- C：标题字体、正文样式、页面设置、页码域、正文与说明保留、无章节硬分页。
- D：真实目录、15 个最终标题及正确页码、目录/正文分页、ODT/PDF SHA-256 回执。
- 联合条件：全部角色检查通过；live/saved 一致且无未保存状态；PDF 与独立原生重导出一致。
- PDF 检查包括逐页文本、页数、实际 PDF 页面尺寸和 72 DPI RGB 渲染。
  像素阈值为平均通道差 ≤ 0.1（0–255）且任一通道差 >8 的像素比例 ≤ 0.001。
- 目录页码额外对照提交 PDF 中的实际标题位置。仅“重新导出得到同样的旧目录”不算合格。
- 保存后的 ODT 以只读挂载进入独立 LibreOffice 评测环境，禁止宏，不更新/修复/保存原文件。
- 退出桌面前只读捕获 live 状态。评测不会替 agent 保存或更新目录。
- `handoff/*.json` 是不可信协调提示，不是成功证据；回执哈希正确也不能替代 PDF 一致性检查。
- D 的报告单列 `unmet_upstream_roles`，不能把上游失败简单归为 D 的独立能力失败。

轨迹仍需人工核验：分工遵守、审计解释真实性、是否伪造证据不能仅靠文件属性证明。
API/应用/评测基础设施错误需单列，不应自动解释成并发冲突。

## 验证与观测

`experiments/validate_writer_conflict.py` 使用真实 Writer/UNO 执行参考操作，**LLM_rollouts = 0**：

- 原始输入和仅 A 完成时均不能通过联合验收。
- `A→B→C→D`、`B→C→A→D` 两种顺序都可通过所有角色和联合检查。
- 未保存 live 修改：磁盘角色检查全部通过，但 live/saved 一致性失败。
- 旧目录：上游全部通过、PDF 与当前 ODT 重导出一致，但目录标题/页码检查失败。
- 旧 PDF 配新正确哈希：上游通过，哈希回执通过，独立重渲染仍能识别过期 PDF。
- 旧文件覆盖：已完成的 B/C 修改回退，被最终状态检查识别。

桌面运行时每 0.5 秒从主机侧只读采样保存版本，不触碰 GUI。
`saved-version-review.json` 报告选定信号（outline、标题、说明）的 true→false 回退，
保留相应 ODT，不用“历史最佳版本”替代最终结果。采样只能提供下界和疑似回退，不能证明因果或不存在瞬时冲突。

## 构建和运行

在 `CoDesk` 下构建独立数据集目录：

```bash
.venv/bin/python -m tasks.weavebench_writer_conflict.spec \
  --seed runs/research/weavebench-official-20261103/dataset \
  --out runs/datasets/weavebench-writer-conflict-20261104-r2

.venv/bin/python -m pytest -q tests/test_weavebench_writer_conflict.py
```

CPU10 原生验证使用冻结镜像 `paragui/weavebench-pairs:20261103`，
image ID `sha256:312f8d9f1b52d7494c98fe2d7fc88c58e818234db4b72a9aa1f2e956364d412e`。
控制器需要 Docker CLI、Docker socket、Pillow/requests；镜像内还提供 Python UNO 和 PDF 工具。
控制器路径必须与宿主一致，agent 桌面只挂载公开 inputs，不能挂载 reference/grade/baseline。

```bash
python3 -m experiments.validate_writer_conflict \
  --dataset "$DATASET" --out "$VALIDATION_OUT"

python3 -m experiments.weavebench_writer_conflict \
  --dataset "$DATASET" --credentials "$CREDENTIALS" \
  --freehand-runtime "$RUNTIME" --codex-binary "$CODEX_BINARY" \
  --harness codex --out "$CODEX_OUT"
```

模型运行器固定为四角色同一波 `abcd`，不提供一/二并发实验选项。
Freehand 用相同命令替换 `--harness freehand`，两个 harness 用各自全新桌面和 pristine inputs，不能共用上一轮结果。
预算沿用每 agent 300 desktop actions / 90 model turns / 1500 秒；实际模型来自冻结 credentials 配置。
原生校验不是模型四并发成绩；本轮只构造并验证工作负载，没有启动 Codex/Freehand 模型实验。
