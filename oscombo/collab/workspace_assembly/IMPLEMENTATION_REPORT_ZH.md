# Workspace Assembly V0 实现报告

## 实现内容

- `TASK_CARD_ZH.md`：完整任务、A/B/Single 指令、共享 workspace 条件、公平性和因果归因边界。
- `fixtures/initial_workspace/`：固定有效 ODT/PNG/PDF/CSV/TXT 输入；`fixtures/private/gold_workspace/`：完整 Gold；`fixture_manifest.json` 固定初始文件 SHA-256。
- `oracle.py`：最终目录路径、附件字节和 SHA、manifest、ODT 原文与超链接解析、非目标完整性。
- `runner.py`：episode 初始化、三条件配置、共享消息/附件协议、评测、provenance、资源所有权与历史保留式 reset。
- `tests/test_workspace_assembly.py`：Gold/Initial、文件与报告负控、消息、reset、条件后端等价和 Writer 序列化回归。

## 验证状态

- 离线 Gold Oracle：PASS；Initial 和定向负例：FAIL as expected。
- LibreOffice UNO headless 在同一 episode 目录打开并保存 Gold ODT 后，报告段落、相对链接、附件路径、文件哈希和完整 Oracle：PASS。
- PNG/PDF/ODT 文件格式检查及附件 SHA：PASS。
- 定向验证：`tests/test_workspace_assembly.py` **11 passed**，包含六类负控、fixture 重建、消息附件、条件 backend 一致性、reset/provenance 和 LibreOffice UNO 同路径 Writer round-trip。
- Guest 文件管理器/Writer GUI、Solo、MA-ID、MA-SD、焦点/文件选择器/剪贴板暴露：`PENDING_GUEST_VALIDATION`。
- 共享 workspace 的双 Guest mount adapter 尚未接入；条件计划声明相同 canonical backend，未把两个独立文件副本冒充等价后端。
