# CPU15 / Docker Codex：免审批工具，保留沙箱

2026-11-13 用户明确要求：**VM 宿主和 Docker 内均不得开启 YOLO，可以放开工具调用权限。**

## 生效配置

CPU15 `~/.codex/config.toml` 使用 [codex.cpu15.toml](../configs/codex.cpu15.toml)：`sandbox_mode="workspace-write"`、`approval_policy="never"`、Shell 工具开启、沙箱内网络开启、App 工具默认 `approve`。这是用户默认配置，不在宿主启动实验智能体。

CPU15 既有 `/etc/codex/requirements.toml` 已只允许 `read-only` / `workspace-write`，本次保留系统管理配置。实验容器另外只读挂载项目的 [codex.requirements.toml](../configs/codex.requirements.toml) 到相同位置，防止普通配置或 CLI 参数选择 `danger-full-access`。

Full GUI+CLI 的既有 MCP 服务均使用 `default_tools_approval_mode="approve"`；Shell 可以在工作区沙箱内直接执行。工具仍受实际挂载、用户权限和容器网络约束，宿主文件与 Docker socket 不因此开放。历史 GUI-only / read-only 对照臂保留原实验动作空间。

## 代码执行路径

- 旧 `container-unrestricted` 参数名保留兼容；现在表示免逐次审批，不表示取消沙箱。权限审计中 `yolo_enabled` / `yolo_equivalent` 均为 false。
- `professional_codex_entry.py` 移除原本的 `danger-full-access` 覆盖，明确用 workspace-write；旧 Guest 配置生成器 `codex_vm10.py` 同样改为 workspace-write。
- Native/WeaveBench、Judge、CoDesk 四臂、Professional races、Astra races 的实验智能体启动参数均加入只读 requirements 挂载。
- CoDesk 容器配置检查禁止两种 YOLO 标志、`danger-full-access` 与 `external-sandbox`，包括嵌套 profile / MCP 参数中的绕过。
- 运行后检查实际 `turn_context`，拒绝取消沙箱、权限不符、模型不符或缺少可核验记录；不会仅凭启动审计声明成功。
- 历史结果和恢复包不改写。旧 `danger-full-access` 运行记录不能作为新策略的 passing preflight；下一轮实验需重新验证。

## 验证边界

本次验证配置解析、启动参数和权限回归测试，并在 CPU15 核对部署文件及用户/系统配置。当前 CPU15 还没有实验镜像和容器 Codex 二进制，没有启动模型实验；实际桌面工具及沙箱在镜像中的兼容性仍需恢复环境后做 smoke。

本地 109 项相关测试通过，覆盖 Native/Hybrid、CoDesk、Astra、Professional races、Guest 配置和图像历史回归，以及新增加的绕过拒绝测试。部署备份和逐文件校验记录保存在 `runs/recovery/20261113-codex-sandbox-policy/`，CPU15 对应 `~/data/paraGUI/archives/recovery-20261113-codex-sandbox-policy/`。

官方配置语义参考：[Sandbox and approvals](https://learn.chatgpt.com/docs/agent-approvals-security)、[Config reference](https://learn.chatgpt.com/docs/config-file/config-reference)。审批策略与沙箱策略分开配置；MCP 的 `approve` 控制工具审批，`allowed_sandbox_modes` 限制可选择的沙箱模式。
