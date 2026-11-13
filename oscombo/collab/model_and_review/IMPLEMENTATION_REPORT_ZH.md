# Model-and-Review 真实 Blender Fixture 实现报告

## 状态

`REAL_BLEND_FIXTURE_AND_BACKGROUND_ORACLE_VALIDATED / GUI_GUEST_PENDING`

已配置官方 Blender 运行时，生成并后台重开真实 initial/Gold `.blend`，完成正式 Oracle 正例、initial 负例、六类真实工程负控、保存重开、runner 评分及 Fixture reset。没有启动 Blender GUI、OSWorld Guest、QEMU、Docker Guest 或模型；本报告不代表 GUI Agent 已完成任务。

## Blender 运行时

- 版本：Blender **5.2.2 LTS**，Linux Release，build hash `d13f752e3b9c`，build date `2026-09-15`；内置 Python `3.13.13`，`bpy` 导入成功。
- 官方 Linux 包：[Blender 5.2 release directory](https://download.blender.org/release/Blender5.2/)
- 下载地址：`https://download.blender.org/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz`
- 官方 SHA-256：`84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168`；下载后 `sha256sum -c` 通过。归档大小 `383,295,504` bytes。
- 个人依赖目录：`/home/mjh/Projects/_deps/blender/blender-5.2.2/blender-5.2.2-linux-x64/blender`。未用 sudo、未改系统 Python/驱动/CUDA，也未修改其他项目环境。
- Blender 仅用 `--background -t 2` 和 `OMP_NUM_THREADS=2`；未执行渲染。

## 真实 Fixture

| 工程 | 路径 | 大小 | SHA-256 | Oracle 结果 |
| --- | --- | ---: | --- | --- |
| initial | `oscombo/collab/model_and_review/fixtures/initial.blend` | 115,947 bytes | `b0053ca0c2199779af99c7e47eda09fd6f1da6b98b5a86dded97635bd2f7760c` | `FAIL`，符合未完成起始状态 |
| Gold（私有） | `oscombo/collab/model_and_review/fixtures/private/gold.blend` | 115,941 bytes | `0cf276d5bd5b186384c846fdb57536f7fb2b8fc18a820641918e206ee0b55051` | `PASS`，所有正式检查通过 |

Gold 目录权限为 `0700`、文件权限为 `0600`。Agent workspace 只使用 initial；不得把 Gold 工程或 `fixtures/private/` 挂载给 Actor。

机器可读版本、下载、生成及 Fixture 哈希记录：`fixtures/blender_fixture_manifest.json`。首次真实运行证据保存在 `audits/model_and_review_blender_smoke/20261022T121313Z/`。

## 生成与读取命令

```bash
export CODESK_BLENDER_BIN=/home/mjh/Projects/_deps/blender/blender-5.2.2/blender-5.2.2-linux-x64/blender
export OMP_NUM_THREADS=2

"$CODESK_BLENDER_BIN" --background --factory-startup -t 2 \
  --python oscombo/collab/model_and_review/blender/build_fixture.py -- \
  --output oscombo/collab/model_and_review/fixtures/initial.blend --variant initial

"$CODESK_BLENDER_BIN" --background --factory-startup -t 2 \
  --python oscombo/collab/model_and_review/blender/build_fixture.py -- \
  --output oscombo/collab/model_and_review/fixtures/private/gold.blend --variant gold
```

`oracle.evaluate_blend_file()` 调用 Blender 后台加载文件，再运行 `blender/snapshot_scene.py` 提取对象、位置、尺寸、网格摘要、材质、相机、灯光和灯罩剖面，最后交给既有正式 Oracle。Gold 实测灯泡径向净空 `0.48375 m`、垂直净空约 `0.13 m`；要求分别为 `0.40 m` 与 `0.10 m`。

## 正例、起始状态和真实 `.blend` 负控

- Gold：`PASS`，`A_geometry=true`、`B_review_presentation=true`，正式检查全部通过。
- Initial：`FAIL`；灯罩尺寸/剖面、灯泡净空、相机及三盏灯尚未达到目标，证明 Oracle 不会把起始工程误判为完成。
- 负控 `.blend` 均由 Gold 在 Blender 中打开、修改并重新保存，不是 normalized JSON：

| 负控 | 结果 | 实际失败检查 |
| --- | --- | --- |
| `dimensions.blend` | `FAIL` | `object:Lamp_Shade`, `shade_mesh_profile` |
| `collision.blend` | `FAIL` | `shade_mesh_profile`, `bulb_clearance`；计算净空 `-0.04 m` |
| `material.blend` | `FAIL` | `object:Lamp_Shade`, `material:Mat_Deep_Green` |
| `camera.blend` | `FAIL` | `camera_presentation` |
| `light.blend` | `FAIL` | `light:Key_Light` |
| `protected.blend` | `FAIL` | `object:Lamp_Base`，非目标基座发生位移 |

六个负控文件和逐项结果位于 `audits/model_and_review_blender_smoke/20261022T121313Z/negative_controls/` 与 `negative_oracle_results.json`。

## 保存、重开与 Reset

1. Blender 后台加载 Gold 并另存为 `roundtrip/gold_roundtrip.blend`；新进程重新打开并运行正式 Oracle，结果 `PASS`，哈希 `1b9ff6aadba4974173e9df0e6f267ac5784239244a683e64ce0a8fa1a0509f7f`。
2. 使用真实 runner `prepare_run → configure_run → RevisionStore checkout/commit → evaluate_run`：提交 revision 1 后正式 Oracle `PASS`。
3. `reset_owned_run` 返回 `RESET_VERIFIED`。恢复文件哈希与原 initial 一致：`b0053ca0c2199779af99c7e47eda09fd6f1da6b98b5a86dded97635bd2f7760c`；旧 workspace 与 revision 归档保留在 smoke run 的 `runner_reset_test/pre_reset/`。
4. 对 reset 后工程运行 Oracle 得到 `FAIL`，这是预期结果：reset 恢复的是本来就未完成的 initial，不是 Gold。没有遗留上一轮 Gold deliverable。

生命周期证据：`audits/model_and_review_blender_smoke/20261022T121313Z/save_reopen_reset_results.json`。

## 兼容性修复与失败记录

- **压缩 `.blend` 文件头：** 首次运行已由 Blender 保存工程，但 5.2.2 默认写出 Zstandard-compressed `.blend`，文件首字节为 Zstandard magic，而非裸 `BLENDER`。原有生成器和 runtime 检查因此拒绝了 Blender 自己刚保存的有效工程。已增加 plain/Zstandard 容器头识别；真实 Oracle 仍必须通过 Blender 打开文件并成功提取场景，因此单独一个 Zstandard 头不会被当成通过。
- **稳定的非目标网格指纹：** 首轮以 initial 为保护基线时，Gold 的 `Lamp_Bulb` 被误报污染。原因是不同 Blender 进程为等价 UV 球网格分配了不同顶点/面索引顺序。现改为基于坐标多重集、边和保留 winding 的规范化面环计算摘要；几何坐标仍以既有快照精度 `1e-6` 记录。**正式尺寸、材质和净空判分容差仍为 `1e-4`，Gold 标准和任务语义未放宽。** initial 与 Gold 的底座、灯杆、灯泡、地面保护指纹现一致。
- Blender 5.2.2 对 `Material.use_nodes` 输出一个面向 Blender 6.0 的弃用警告；本次工程生成、保存、重开和检查均成功。该警告不是本轮失败。

## 回归测试

运行命令：

```bash
CODESK_BLENDER_BIN=/home/mjh/Projects/_deps/blender/blender-5.2.2/blender-5.2.2-linux-x64/blender \
OMP_NUM_THREADS=2 python -m pytest -q \
  tests/test_model_and_review.py tests/test_data_to_deck.py \
  tests/test_ticket_to_resolution.py tests/test_build_and_verify.py \
  tests/test_timeline_and_assets.py
```

结果：**89 passed in 17.08s**，包含以真实 initial/Gold `.blend` 运行的背景 Oracle 测试。前四个协作 Case 的离线回归均通过；其任务语义和历史结果没有修改。

## 尚未验证

- Blender GUI 的可操作性、桌面状态采样是否无扰动、OSWorld Guest 的 Blender 安装与显卡/显示兼容：`PENDING_GUEST_GUI_SMOKE`。
- Single-Agent GUI、Collaborative-Isolated、Collaborative-Shared、自然暴露/干扰/恢复及真实 Agent：均未运行。
- 本轮成功仅覆盖真实 Blender 后台文件生成、解析、Oracle、文件 roundtrip 和本地 fixture reset；**不构成 GUI Agent 成功或 Guest smoke 通过**。
