# Spreadsheet Handoff V0 实现报告

## 交付内容

- `spec.py` / `TASK_CARD_ZH.md`：Case ID `CDD-SH-001`、完整 A/B/Single 指令、规则与条件语义。
- `fixtures/initial.ods`、`fixtures/private/gold.ods`：真实 ODF Spreadsheet 容器，Gold 有 Calc 公式与缓存值；manifest 固定 SHA-256。
- `oracle.py`：保护源表、预测、采购、预算、公式、跨角色一致性；值解析和浮点比较复用 Data-to-Deck Oracle。
- `workbook_store.py`：append-only ODS revision、单写租约、revision/hash CAS、历史保留式 reset。
- `runner.py`：prepare/configure/evaluate/reset、消息服务、资源账本和 provenance；离线路径不声明 GUI trace。
- `tests/test_spreadsheet_handoff.py`：正负控、ODF/Calc 序列化、租约、消息、reset 和配置测试。

## 验证边界

生成的 ODS 可被 Data-to-Deck `read_ods` 读取；正控 Gold oracle PASS、初始工作簿 FAIL。LibreOffice headless 打开/另存为 ODS 后，公式位置与语义、值、source sheets、跨角色一致性和预算检查仍 PASS。整数金额精确比较，非整数浮点只用旧 Oracle 的 `1e-15` 容差。Guest、真实 GUI、模型及自然协作均未验证。

Fixture 重建（输出目录必须不存在或为空）：

```bash
python -m oscombo.collab.spreadsheet_handoff build-fixture /tmp/codesk-sh-fixture
```

定向验证：`tests/test_spreadsheet_handoff.py` **13 passed**，包含公式位置与数值负控、零净需求、单写 lease/CAS/reset、消息附件、三条件后端/预算一致性和真实 LibreOffice ODS round-trip。通过不代表 Calc Guest GUI、Solo Agent、MA-ID 或 MA-SD 已通过。
