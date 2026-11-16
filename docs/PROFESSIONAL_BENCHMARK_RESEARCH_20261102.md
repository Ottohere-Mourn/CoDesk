# 专业软件 benchmark 与轨迹调研（2026-11-02）

## 2026-11-03 范式修正

用户明确：paraGUI 支持 GUI **以及 CLI/编程**，不能因为是 GUI benchmark 就禁止
Codex/Freehand 使用脚本、应用 API 或控制台。主条件采用 hybrid；GUI-only 仅作为显式消融。
下面的来源观察不变，但不再把 WeaveBench 的混合工作流视为主实验之外的例外。
六对原创任务已补充可选的编程工作流；没有新增或改写任何历史 agent 成绩。

## 结论与证据边界

这次不是仅根据 benchmark 名字造题：下载并统计了 WeaveBench 的 6 条公开轨迹、
Refresh BlenderBench 的 1 条 ATIF 轨迹；检查了 QGIS、CloudCompare 的实际桌面截图；
阅读了 CADWorld 的 Sketch、Part、TechDraw 任务配置和动作/评分契约。
其他 Blender 系列只核对官方论文、项目页或仓库，不声称看过它们的完整 rollout。

**专业软件任务不等于纯 GUI 任务。** 要区分鼠标键盘操作、`bpy`/CLI 编辑以及混合轨迹。
paraGUI 主实验仍是两个独立 agent、同一桌面、同一应用进程、同一原生项目；
不能用两个独立桌面或互不共享最终状态的独立脚本任务替代这个实验；
在共享环境中用脚本解题、辅助 CLI 进程处理数据及 GUI 核验都允许。

新题是 **benchmark 工作流启发的原创合成任务**，不是官方 benchmark 的改编实例或子集。
没有复制它们的原生资产、参考解或完整题目。旧 p1–p3 及其评分、失败运行保持不变。

## 官方来源对照

| 来源 | 任务/轨迹形态 | 对 paraGUI 的价值 | 本次证据层级 |
| --- | --- | --- | --- |
| WeaveBench [W] | 114 题；GUI 与 CLI/code 的长流程交替；独立 judge 同时看结果和过程 | 主条件直接学习其混合工作流：原生文件、导出物、错误恢复、跨界面核验 | 6 个原始 JSON + gallery 计数逻辑 + 2 张实际桌面截图 |
| Refresh BlenderBench [R] | 20 种 Blender 工作流，包括已有场景修改、材质、动画、绑定、相机、模拟 | 给定半成品，明确可改/不可改，考察专业工作流而非只生成漂亮图片 | 1 条完整公开 ATIF + 官方任务/评分说明 |
| CADWorld [C] | FreeCAD 截图/pyautogui 操作，保存 `.FCStd` 后独立检查 | Sketcher 约束、原生特征、TechDraw 结构；最贴近纯 GUI 的设计 | 3 个任务配置、动作契约、评分契约；未验证完整公开 rollout |
| BlenderGym [G] | 官方页列 245 个手工场景；修改 Python，让起始场景接近目标场景 | 程序几何、灯光、材质、形变、布局的分类和起始/目标对 | 官方项目页与论文；不是纯 GUI 基线 |
| BlenderAlchemy [A] | 编辑脚本、渲染、视觉评估、选择候选，再迭代 | 保存中间候选和回退记录；属于方法，不冒充 GUI benchmark | 官方代码入口及日志/候选输出说明 |
| VIGA 的 BlenderBench [V] | visual-to-code；code → render → inspect → edit | 多轮视觉校验、保留可编辑程序/项目 | 官方论文；与 Refresh 同名但不是同一个数据集 |
| BlenderWorld [B] | 223 个文本/图像/视频/结构化需求任务，多视图渲染及任务级 rubric | 多视角、空间关系、保留原资产的检查方式 | 官方论文；未验证公开逐动作轨迹，不归为 GUI-only |

不使用搜索时命中但标题不符的 arXiv 链接。BlenderWorld 本次核对的是
`2610.23986`，BlenderGym 是 `2504.01786`；“Blender Benchmark”硬件跑分不在此范围。

## 实际抽样轨迹：不能把 step 当成点击次数

下面是 `steps[].kind` 的逐条统计，**不是重新运行这些模型得到的结果**。
WeaveBench 的 `cli` 也可能包含 `xdotool` 或截图命令；一个 `gui` 事件可能有多个点击。
`note` 是非工具事件，报告不转录模型内部推理。

| WeaveBench task_id | 原始事件 | gui | cli | note | 附截图事件 | 去掉 note 后的通道切换 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SPA_task_0_blender_room_arrange | 32 | 1 | 31 | 0 | 1 | 1 |
| DES_task_15_blender_bpy_lookdev_eyedrop | 20 | 0 | 20 | 0 | 0 | 0 |
| SPA_task_1_qgis_flood_zone | 210 | 89 | 31 | 90 | 89 | 32 |
| SPA_task_2_kicad_pcb_route | 105 | 39 | 66 | 0 | 39 | 32 |
| SPA_task_13_meshlab_printability_audit | 59 | 8 | 42 | 9 | 8 | 12 |
| SPA_task_14_cloudcompare_scan_vs_cad | 155 | 40 | 47 | 68 | 40 | 18 |

Gallery 的 QGIS “120 steps” = 89 + 31，不包括 90 条 note；CloudCompare 的 87 也是同理。
前端合并相邻 note，并只给非 note 编号。我们的 primitive action 数、它的 numbered event 数、
ATIF 的 step 数必须分栏，不能直接比较效率。

### 可观察的工作流程

- **Blender room**：初始桌面观察 → 文件/资产检查 → 写 `bpy` 脚本 → 后台建场景及渲染 →
  检查布局与文件 → 修改再渲染。唯一 gui 标签事件是 `(no-op)`，不能称为 32 步纯 GUI 建模。
- **Blender lookdev**：本条轨迹停留在图像分析、环境/依赖检查和安装尝试；0 个 gui 标签事件。
  这是失败/未完成样例，不能从题目要求倒推出已执行的 eyedrop GUI 流程。
- **QGIS flood**：先检查空间数据并用脚本生成分析/布局，再进入 QGIS 查看图层、分类、
  属性和布局、保存证据。所看的截图是真实布局编辑器，但截图本身不能证明前序计算靠 GUI 完成。
- **KiCad**：板/原理图/规则检查 → 环境准备和脚本/文件操作 → GUI 检查 DRC、板图及截图 →
  输出检查。不能把依赖安装时长解释为并行 GUI 干扰。
- **MeshLab**：网格检查/修复脚本与 Python viewer 操作交错。看到“有截图”不能自动认定是在
  MeshLab 原生界面完成全部修复；正式审计需核对窗口和进程身份。
- **CloudCompare**：点云/名义模型检查 → CLI 处理及距离计算 → GUI 标量场、截面/视图检查 →
  报告及导出。本次看的截图显示 CloudCompare 截面操作窗口。

这些是有目的的 6 条专业软件抽样，**不代表整个 benchmark 的 GUI 占比或成功率**。

### Refresh 的 ring-box 绑定/动画样例

公开 trial `blender-image-kitchen-rigging__jYHU2au`，ATIF-v1.8：
38 个 step = 1 个用户 step + 37 个 agent step；显式工具调用 29 个，其中
`bash_command` 28 个、`mark_task_complete` 1 个；另外有 8 个图像 observation block。

可见动作是提取参考视频帧、分析原始网格、生成绑定/动画脚本、后台渲染、检查视频和最终文件。
因此应描述成 **代码主导且带视觉观察的工作流**，而不是鼠标完成的 38 步 GUI 绑定。
导出中的部分图像 step 没有显式 tool_call，不能擅自补齐工具调用或以此证明从未操作桌面。
本次未解包 Refresh 的截图 chunk；看过完整结构化轨迹，不声称逐帧看过该视频/全部图片。

### CADWorld 的可借鉴之处

读取了 `freecad-sketch-001`、`freecad-part-001`、`freecad-techdraw-001`。
任务配置把输入准备、agent 操作、结果提取和 host-side 评分分开。
Sketch 示例检验几何关系；TechDraw 示例检验页面/投影视图/局部视图等文档结构。
它的 `traj.jsonl` 区分原始输出和 sanitized/executed action；不合法动作可变为 `WAIT`。
我们也应保留“模型请求了什么”和“实际执行了什么”，不能只保留屏幕录像。
原生 evaluator 不等于无漏洞，某些标签匹配仍需审计；也不能把动作白名单当成绝对阻止 GUI 控制台。

## 据此新增的六对原创规格

完整参数、A/B 权限范围、输出和验收项在 `tasks/professional_v2/catalog.json`。

| ID | 软件 | A | B | 状态 |
| --- | --- | --- | --- | --- |
| p4 | Blender | 独立盒盖的铰链关键帧和线性运动 | 另一产品外壳与旋钮的材质定稿 | 原生参考解与 GUI 重开验证通过；未跑 agent |
| p5 | Blender | 支架的非破坏 bevel/mirror 建模 | 独立标牌的 UV 岛和贴图布局 | 规格草案，未生成资产 |
| p6 | FreeCAD | 夹具底板的约束草图、孔与实体 | 独立衬套的参数化建模及 TechDraw | 规格草案，未生成资产 |
| p7 | QGIS | 地块高程统计、风险字段和导出 | 不引用风险结果的巡检线路和固定图层布局 | 规格草案，未生成资产 |
| p8 | KiCad | 固定元件/网络的铜线布线 | 板上独立区域的丝印与装配说明 | 扩展草案，当前 harness 未接入该软件 |
| p9 | CloudCompare | 扫描 A 对名义 A 的配准/偏差 | 独立扫描 B 的截面、标量范围与导出 | 扩展草案，当前 harness 未接入该软件 |

“理想流程”只是作者设计的步骤，不是实测 agent trajectory。六对规格不等于六对可跑 case。
首对 p4 的脚本参考验证也不等于真实 GUI agent 通过；默认不注册到旧 p1–p3 批次。

p4 的 r2 原生验证于 16:22:52 UTC 完成：A-only、B-only 各自目标通过；A→B 和 B→A
均为 A=6/6、B=6/6，提取的目标语义状态一致。三个负向检查和两个真实 GUI 重开检查通过。
初始状态的 A=3/6、B=2/6 来自保留/有效性项目，不表示初始已经完成编辑。
首轮 r1 的初始截图截到了灰色未绘制窗口；保留原记录，补充非空就绪检测后在新目录重验。
完整评分、哈希和局限见 `tasks/professional_v2/README.md` 的 validation record。

## paraGUI 的录制与评分约束

1. 每个角色有明确语义写入范围。共同保存文件是允许共享的；不能用整个文件字节哈希要求 A/B 独立。
2. 先验收 A-only、B-only、A→B、B→A：两个顺序的**目标语义状态**相同，角色之间无必需的先后依赖。
   这只能证明目标兼容，不能证明焦点/模态窗口/选择状态可安全并行。
3. 单 agent、共享桌面顺序 A→B/B→A、共享桌面双 agent 并行应使用同一输入、工具权限、模型预算。
   并行成功率和 makespan 分开报告，另记 token、429/重试/环境失败；不只给速度比。
4. 每个角色的 6 项是可解释的 rubric，不是“完成了 6 个 agent”。同时保留硬性完整性 gate、
   共享最终状态的两个分数，以及双方全通过率。固定检查项的保留项可以在初始状态就得分。
5. 优先检查可编辑原生结构、几何/数值容差、导出后重开；视觉检查覆盖关键视角/帧。
   不靠文件存在、单张截图、SVG 字面 `<circle>` 或固定说明句子来替代实质正确性。
6. 保存 action 请求/执行、动作前后焦点、观察截图及时间、保存/导出事件、原生文件哈希。
   focus、active object、editor/workbench、frame、modal dialog 是预期的共享干扰面。
   混合轨迹另记录命令、stdout/stderr、退出码、超时、GUI/CLI 通道以及文件覆盖/缓存冲突。
7. 评分器/参考解/私有断言不得挂载进 agent 容器。主条件允许 terminal、Python console、脚本编辑器
   和编程解题，不因使用代码扣分。GUI-only 仅作单独标注的消融；其提示词禁令不是 OS 级隔离。
8. 本机和 VM host 不启用 YOLO 或等价配置；若后续使用 container-unrestricted，仅允许在已审计的
   实验 Docker 内。本次造题/验证不调用 Codex，不修改任何主机 Codex 配置。

## 复现及来源

原始下载在被 git 忽略的 `runs/research/professional-benchmarks-20261102/raw/`，
统计与 SHA-256 在同目录上级 `evidence.json`。重算：

```bash
python3 experiments/audit_professional_benchmarks.py \
  runs/research/professional-benchmarks-20261102/raw \
  --out runs/research/professional-benchmarks-20261102/evidence.json
```

WeaveBench 仓库快照：`acf203ae24386aa9bcc0da950c533c8c796dc38e`。
CADWorld 仓库快照：`5e9529ff984b5426a5c194b94a09dc84cbe7fa7a`。
网站轨迹可能随时更新；复查时应核对 evidence 中的字节哈希。
公开下载只用于本地研究；未将其完整 prompt、思考文本、参考资产打进新题。

- [W] `https://weavebench.github.io/`；`https://weavebench.github.io/trajectories/`
- [W-data] `https://weavebench.github.io/trajectories/data/<task_id>.json`
- [R] `https://refresh.dev/blog/blenderbench`
- [R-export] `https://api.trajectories.sh/api/public/trajectories/d701f96e-8132-485a-80f3-654dea6178ee/export`
- [C] `https://github.com/Zdong104/CADWORLD`；该 commit 下 `docs/MODEL_OUTPUT_CONTRACT.md` 与 `evaluation_examples/examples/`
- [G] `https://blendergym.github.io/`；`https://arxiv.org/abs/2504.01786`
- [A] `https://github.com/ianhuang0630/BlenderAlchemyOfficial`
- [V] `https://arxiv.org/abs/2601.11109`
- [B] `https://arxiv.org/abs/2610.23986`

## 同步实验快照

2026-11-02 16:10 UTC 查询：旧 native Codex r2 批次已经 `stopped_on_error`，
QGIS 公共最终状态 A=6/6、B=3/6，状态分别为 completed/error；Blender 和 FreeCAD pending。
这里不推断错误归因，也不自动覆盖/重跑失败实验。完整记录仍在
`/data/yuke/paraGUI/comparisons/professional-native-container-20261102-r2/`。
