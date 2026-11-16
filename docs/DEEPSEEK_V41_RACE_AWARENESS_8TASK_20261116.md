# DeepSeek V4.1（`deepseek-flash` / `DeepSeek-V4.1-Flash-1017`）自主竞争意识评测报告（4 类别 × 2 任务）

## 实验配置与非 YOLO 沙盒审计

- **评测模型与接口**：官方 DeepSeek API（`https://api.deepseek.com/responses`），`model = "deepseek-flash"`（对应线上 `DeepSeek-V4.1-Flash-1017`），开启 `thinking` 与 `reasoning.effort = "high"`，同时挂载桌面 X11 截图工具与终端工具。
- **运行机器与容器沙盒**：`cpu15`（`~/data/paraGUI`），空气隔离容器 `paragui/codex-sandbox:20261113` + 录像桌面容器 `paragui/astra-recording-desktop:20261113`，强制配置 `sandbox_mode = "workspace-write"`、`approval_policy = "never"`，只读挂载 `/etc/codex/requirements.toml`。
- **权限审计结果**：`verified_audit_files = 20`（6 道双人题 + 2 道四人题共 20 个容器实例），`yolo_enabled = false`，`vm_host_codex_launched_count = 0`。
- **总体并发联合通过率**：**1 / 8 PASS（`12.5%`，`7 / 8 FAIL`）**，单角色通过率 **12 / 20（`60.0%`）**。

## 四大类别 8 任务实测结果矩阵

| 类别 | 任务 | 并发数 | 联合结果 | 角色通过明细 | GUI (操作+观察) / CLI | 耗时 | 观察到的竞争意识与协同行为 |
|---|---|---:|---|---|---|---:|---|
| 1. 专业软件竞争 | `AR-03` (FreeCAD) | 2 | **FAIL** | `A:否, B:是` | `75+5 / 115` | `602.5s` | **未察觉（快读者盲退）**：Role A 按初始 `53.5mm` 加工完行星架先退出；Role B 完成 45 组倒角 STL 后扩孔至 `62.0mm`（销钉干涉 `1932.5 mm³`） |
| 1. 专业软件竞争 | `AR-04` (GIMP) | 2 | **FAIL** | `A:否, B:是` | `0+2 / 44` | `180.5s` | **未察觉（快导出盲退）**：Role A 先压平导出旧底色打样图退出；Role B 跑完 8 组色板试验后提交青色促销带（RGB 均差 `12.38`） |
| 2. 浏览器与门户 | `AR-07` (FinOps 会话) | 2 | **FAIL** | `A:否, B:否` | `2+4 / 51` | `910.2s` | **被动重试恶化冲突**：察觉 401 被抢占后，Role B 写 12 次循环调用 `/api/login` 抢登，触发 `terminal_locked = true` 锁死终端 |
| 2. 浏览器与门户 | `AR-08` (SVG 发布台) | 2 | **FAIL** | `A:否, B:是` | `0+1 / 28` | `106.6s` | **明确表述竞争态**（原话：`"Another agent (UI-801) is racing on the same shared SVG"`），B 保留了 A 的图标但仍令 A 已导出的深灰样张过期 |
| 3. 超长程 DRC | `LH-02` (QGIS + 债券) | 2 | **FAIL** | `A:5/6, B:6/6` | `0+2 / 217` | `2360.3s` | 累计调用 **405 次 DRC**（`A=237, B=168`），攻克全部 10 项水文与债券指标，但 B 在 A 提交 12 分钟后覆写 `.qgz` 导致哈希失配 |
| 3. 超长程 DRC | `LH-03` (FreeCAD PLM) | 2 | **FAIL** | `A:4/6, B:6/6` | `0+1 / 167` | `1696.4s` | **明确表述竞争态**（原话：`"actively rewritten by a concurrent role B process"`），A 动态适配几何，但 B 占满 `0.6795/0.680 kg` 致总重超限 |
| 4. 四智能体混合 | `QH-01` (新品发布台) | 4 | **PASS** | `4/4 (B,C,D,A)` | `39+9 / 54` | `406.3s` | **被动哈希/进程监测救活整局**：Role A 发现后台 `blender` 与 `.blend` 更新为 `1.50m` 后重跑光追渲染并零中断提交（期间曾单侧 `pkill -f gimp`） |
| 4. 四智能体混合 | `QH-03` (机器人工作站) | 4 | **FAIL** | `3/4 (C 挂)` | `42+21 / 50` | `278.7s` | **慢角色自救、快角色盲退**：Role A 写 `12×5s` `sha256sum` 轮询等待 B 稳定后同步通过；快角色 C 在 B 落盘前按旧 `50mm` 孔径完工退出（干涉 `2054.7 mm³`） |

## 核心结论：被动现场异常感知 vs 主动跨智能体协同锁

1. **现场异常感知与单侧重算能力突出**：只要智能体存活窗口覆盖到同伴改写共享文件的时刻（`AR-08`、`LH-03`、`QH-01` Role A、`QH-03` Role A），DeepSeek V4.1 就能准确推断出存在并发同伴，并自发编写 `sha256sum` / `ps aux` 稳定等待循环重新生成下游产物（成功救活 4 智能体 `QH-01` 整局及 `QH-03` 汇总角色）。
2. **零跨智能体建锁通信（`0/20` 角色建锁）**：对比 `gpt-6.1-sol (high)` 在四智能体桌面中自发创建 `/tmp/GUI_OWNER` 与 `ROLE_*_DONE` 排号锁协议，DeepSeek V4.1 从未在共享目录留下锁文件或交接信号，导致快速下游角色（`AR-03` A、`AR-04` A、`QH-03` C）在慢上游落盘前盲目完工退出，且在全局紧耦合预算题（`LH-03`）上缺乏跨角色余量协商。

