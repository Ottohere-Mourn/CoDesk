# CRM-LU1 客户主档字段丢失更新：下一阶段静态合同审计（2026-11-06）

状态：**候选设计 / 未实现 / 未跑 Guest / 未调用模型。** 本文不计达标案例，不声称现实 CRM 一般具有此行为。选择本候选，是因为 DATA-REL1 已有一次 PAY-1 风格 tuple，而此候选可测试不同的终态错误签名：一个字段正确保存，却覆盖另一 Agent 已合法更新的字段。

## 先决结论

目前工作路径和本机可见 CoDesk 项目中，没有可复用 CRM 客户主档实现或已经验证的全记录表单行为。本地检索未发现 `CRM-LU1`、billing-email/renewal-contact fixture。若为本候选新建一个“总是最后写入覆盖”的 custom app，再把结果当作真实 CRM 证据，则外部效度不足；不能把模拟器行为包装成已发现的共享桌面普遍风险。

因此本卡只冻结可证伪的任务与语义 gate。**下一步不应立刻搭 UI 或跑 Guest。** 只有找到普通应用的可审计、默认全记录保存语义，且该语义并非为追 FAIL 临时移除的并发保护，才能进入实现。若找不到，CRM-LU1 当前版 no-go；改用其他候选，不以定制 blind-write API 补漏洞。

## 业务流程与单一机制假设

一家小型 B2B 服务团队在客户主档里维护多个日常字段：续约联系人、账单邮箱、有效合同/状态。续约专员 A 根据已签续约单修改联系人；账款专员 B 根据已验证的退信/客户更新通知修改账单邮箱。两个更新都合法，字段职责不同，但同一个主档有一个共同完整编辑表单。唯一目标机制是**过期完整表单保存造成 lost update**，不包含焦点、活动行、剪贴板、tab 或键盘误路由。

固定合成数据：客户 `C-014` 初始为 `renewal_contact=C0`、`billing_email=E0`。A 的凭证给出 `C1`，B 的凭证给出 `E1`。更新后最终有效主档应为 `{C1,E1}`，主键 `C-014` 不变，来源审计各有一条。

| 条件/时点 | 工作区状态 | actor-local 目标 | 同一 oracle 结果 |
|---|---|---|---|
| MA-ID / A 私有 workspace | A 保存 `{C1,E0}` | renewal contact = C1 | A PASS |
| MA-ID / B 私有 workspace | B 保存 `{C0,E1}` | billing email = E1 | B PASS |
| Shared / B 先保存 | `{C0,E1}` | B 的授权账单邮箱修改已完成 | B PASS |
| Shared / A 用先前加载的完整表单后保存 | `{C1,E0}` | A contact=C1；B email=E1 | A PASS、B FAIL、aggregate FAIL |
| Shared(+Lock) / A 刷新、合并字段后提交 | `{C1,E1}` | 两个 owner 字段均正确 | A/B PASS |

MA-ID 的两个 oracle 分别只评自己的 clone；Shared 的 actor-local oracle 分别在同一最终状态上评 A/B 的目标。oracle 不读实验臂；所有 conditions 用同一 `evaluate_actor(workspace, role)`。这种 completion-order 终态评分必须显式报告：B 结束时正确的字段后来被 A 的 stale save 覆盖，并非 B 当时输入错误。

## 必须先证明的产品语义

1. 普通 UI `Save profile` 默认提交整个已加载主档，而不只是修改字段。
2. 保存后端正常接受 stale full form；应用没有默认版本校验、冲突拒绝、字段级合并、PATCH 或自动 refresh。
3. 上述行为属于选用应用的正常公开语义，不是实验时关闭并发保护、绕过校验或自己写的 blind `PUT`。
4. 保存被接受后，审计/最终状态可精确表明 B 的 E1 被 A 的 stale E0 覆盖；错误不得靠活动单元格、焦点/浏览器标签、地址栏或 CLI 文件覆写造成。
5. 正常刷新、重开、字段合并/重做、恢复路径保持可用；恢复成功判 PASS。

单纯找到普通 HTML form 不足以证明语义。一个仅供 benchmark 写的 app 可以作为 *formalized legacy-CRM test fixture*，但即使能达成预期，也只能宣称“该明确设定的 legacy full-record-save 场景”结果，不能宣称现实 CRM 发生率或产品普遍缺陷。若要当作主要论文 case，应优先基于已有产品或明确来源的默认产品行为。

## 共享 schedule 与协议约束

候选固定 schedule 需通过真实 GUI MCP 验证，而非在 oracle 内直接排列状态：A 打开 C-014 的完整表单，修改本地 renewal contact，并形成尚未提交的正常保存动作；B 在另一个稳定表单上下文修改并保存 billing email；之后 A 的同一待提交完整表单保存。Shared+Lock 可以阻塞 A 的单次 submit 调用、让 B 先获得逐动作锁再放行 A；不得替换 A 的参数、表单或 oracle。若 Shared+Lock 的 GUI Context/MCP 使 A 的表单在 B 操作时消失，或者两 actor 通过切换窗口才会造成错误，则有 focus/context 混淆，应 no-go。

同一三臂权限为 GUI MCP、restricted Guest CLI MCP、Collaboration MCP；CLI 只能做 Guest-local 只读核验，不提供更改服务数据库的捷径。模型/端点、task hash、fixture、提示、预算、reset、actor 数、handoff 和评分合同锁定一致。先 MA-ID exact PASS，才可跑 Shared，再 Shared+Lock；单组三臂只是筛查。

## 恢复及负正控

- 正控：A-only 保存 contact 后 PASS；B-only 保存 email 后 PASS；双字段 golden record PASS；普通重载/字段合并最终 PASS。
- 机制负控：记录 C-014 unchanged/错 ID 必须失败；A stale whole-form save 后必须精确显示 B 的 E1 被覆盖；若服务拒绝 stale write，结果 PASS/候选无暴露，不能叫模型 FAIL。
- 恢复：A reload 后读取 E1、重新应用 contact C1，最终 `{C1,E1}`，必须 PASS，B 目标也 PASS。
- 轨迹：保存前表单读取版本/字段、B 保存事件、A 保存请求体/结果、最终 record、审计日志、截图均带时间戳。若不能区分业务状态变化与 UI/agent 输出错误，停止归因。

## 进入 Guest / 模型实验的门

1. 静态确认一个自然使用场景及现成软件/版本。记录产品语义来源与明确外部效度边界。
2. 在小型无模型 fixture 中跑完整保存、冲突保护、刷新恢复各一个 scripted control；只在应用默认设置触发完整表单正常覆盖时继续。
3. 用实际 production MCP GUI/PerActionLock 证明 MA-ID 的 stale 表单状态隔离、Shared+Lock 的相同表单按计划保存，且没有窗口焦点/活动控件混杂。
4. 仅运行一次 GPT-6-Sol MA-ID gate；两 actor 都 exact PASS 且 run valid 才开 Shared arms。允许自然恢复，结果 PASS，不追加特意障碍。

## 决定 / 优先级

- 研究价值：高（丢失更新是不同于 DATA-REL1 stale artifact 的失败签名；可解释、可审计）。
- 实用性：高（多个职能维护客户主档很常见），但目前只是场景合理性判断，不是行业频率证据。
- 与已达标 9-case 的机制距离：预期中高；需最后对照完整 handoff，避免它只是已有焦点/选区或文件共享机制的换皮。
- 主要工程/有效性风险：缺真实默认全记录写入应用，及多 actor 同一表单提交的 UI schedule。
- 当前决定：**保留为有条件的静态候选；未通过产品语义 gate，不进 Guest、模型队列，不计 case 数。若外部默认语义无法核实，则 NO-GO。**

## Read-only product-semantics source check

A targeted public-source review supports the existence of this failure class but also shows why the product/version gate is mandatory:

- A SuiteCRM community thread describes two sessions editing one Account: a later stale save could overwrite a prior user's changes. The same thread says the poster's SuiteCRM 7.7.8 deployment did not show a conflict message, while the latest version they tested did show an optimistic-lock conflict dialog: https://community.suitecrm.com/t/multiple-users-edit-same-record-stop-edit-or-override/68882
- SuiteCRM PR #3276, merged 2018, explicitly fixes an optimistic-locking edge case where the wrong related-record ID could allow a later stale save to overwrite earlier changes; the PR's expected behavior is a conflict dialog: https://github.com/salesagility/SuiteCRM/pull/3276

Interpretation: lost update is a real product failure class in some legacy/edge circumstances, not a general default CRM behavior. Selecting an old version or known locking bug solely to force exposure would be weak evidence. Before implementation, pick one ordinary pinned product version and verify its default edit/save behavior. If it detects stale edits, CRM-LU1 should be dropped or reported as a protected/negative case, not modified to bypass the guard.