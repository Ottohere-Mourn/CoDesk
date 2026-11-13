# CDD-TLA-001 离线实现报告

## 状态

首个确定性 Timeline-and-Assets Case 已有离线 fixture、MLT XML 解析 Oracle、条件计划、provenance、消息 API 绑定和自动化测试。**本轮没有启动 Kdenlive、Guest/QEMU、模型或 GPU。** 真实 Kdenlive open/save、GUI 可解性、Solo、MA-ID、MA-SD 均为 `PENDING_GUEST_VALIDATION`。

## 实现结构

- `TASK_CARD_ZH.md`：唯一任务规格、A/B/S 指令、Gold、条件与归因边界。
- `spec.py`：固定任务常量、公开素材目录、角色指令、私有 gold。
- `template/assets/`：4 个小型合成 MP4 源片与 10 秒 WAV 音乐床；`fixture_sha256.json` 留固定哈希。
- `template/project/GreenLoop.kdenlive` + `.srt`：含 V1 两镜头、A1 短音乐和不完整字幕的初始工程。
- `fixture.py` / `media_fixture.py`：固定工程构造与可选媒体再生成器。
- `mlt_project.py`：本 Case 使用的 MLT XML serializer/parser；不宣称通用 Kdenlive 编辑库。
- `oracle.py`：镜头清单、工程轨道/源区间/位置、时长、字幕 filter/SRT、素材箱完整性及受保护文件的独立评分。
- `runner.py`：离线 run setup、Single/MA-ID/MA-SD 计划、消息/附件初始化、provenance、ownership-checked reset 与 CLI。
- `integration.py`：复用 Data-to-Deck 既有 actor-scoped ProtocolStore token binding。
- `interaction_event.schema.json` / `interaction_log.py`：未来 Guest 采集的 actor、截图、窗口、监视器/播放头/轨道/选中对象事件契约。当前仅提供安全 append API，不读取 Kdenlive GUI 状态。
- `shot_manifest.schema.json`：A 的机器可读交付格式。
- `instance_schema.json`：run/condition/backend/fixture/Actor/ownership provenance manifest 结构。
- `tests/test_timeline_and_assets.py`：正负控、结构解析、条件、消息和 reset 测试。

## 工程格式可靠性

Kdenlive 官方文档描述当前项目结构为 MLT XML；时间线由轨道 tractor 和 playlist/entry 构成；字幕通过 `avfilter.subtitles` 与同名 `.srt` sidecar 表示。当前离线工程据此生成 MLT XML，精确到 25 fps 帧，并解析同一子集。固定媒体由 PyAV/OpenCV 在本机生成；每段有可见的 leader/action/tail 区间，因此 A 的 in/out 选择有素材内证据，不是任意数值。资产 SHA-256 固定。画面是低分辨率合成素材，验证重点是实际剪辑软件状态操作，不代表真实商业视频审片能力。

格式依据：[Kdenlive project file format](https://github.com/KDE/kdenlive/blob/master/dev-docs/fileformat.md)、[MLT XML format](https://mltframework.org/docs/mltxml/)。Kdenlive 的 track tractor/playlist 结构和 subtitle filter 表示以其官方格式文档为准。

证据边界：本机未发现 `kdenlive` 或 `melt` 可执行文件；因此这里只证明 XML 语法可解析、Oracle 对本 Case 表示可判定，不证明当前 Kdenlive 版本可无警告打开、保留元数据、正确显示字幕、解码媒体或 round-trip 保存。需要真实 Guest Gate：Kdenlive 打开初始工程 → 预览四个片段 → 通过 GUI 编辑并另存 → 关闭/重开 → 检查轨道/播放头/字幕/音频 → 对输出工程评分。

## Oracle 与测试

Oracle 独立检查：

1. A 的三个 shot ID、源入/出帧、顺序、选择理由和 outtake 排除；
2. B 工程 V1 每个 source/position/track，A1 音乐区间和 250 帧总时长；
3. 工程字幕 filter 与三条精确 SRT cue；
4. 所有素材均留在 project bin，ASSET-04 不进 timeline；
5. brief/catalog/初始 project/SRT/固定媒体哈希不被篡改。

执行结果：`python -m py_compile oscombo/collab/timeline_and_assets/*.py` PASS；`python -m pytest -q tests/test_timeline_and_assets.py` **17 passed**；全仓 `python -m pytest -q` **117 passed**；`git diff --check` PASS；本 Case Markdown 相对链接 0 broken，文本文件尾随空白 0。另用当前 PyAV 16.0.1/OpenCV 解码确认四段 MP4 的帧数分别为 150/175/125/125、分辨率 320×180、25 fps，WAV 为 10 秒/48 kHz/双声道；在当前同环境重复生成与固定媒体的字节 SHA-256 一致。全仓测试包含既有用例，本报告未修改前三个 Case。

负控包含错序、错 source range、错轨、总长错误、错字幕、缺 audio、缺 outtake bin entry、outtake timeline contamination、损坏素材和缺少清单。脚本构造的正确工程是 Oracle 测试 positive control，不是 Agent 或 GUI 结果。

## 协作/干扰证据边界

条件计划给三种模式绑定同一 `workspace_backend_id`。A 只产出 asset shot manifest，B 只产出最终项目，避免竞争写同一输出文件。Shared 中 Clip Monitor/Project Bin 与 Timeline 共享单个 Kdenlive session，因此存在 source selection、source/timeline playhead、active monitor、selected timeline clip/track 状态暴露机会，但不保证自然发生。事件 schema 可表达 based-on-observation、意图/结果对象、窗口非原子采样与截图 hash；`interaction_log.py` 只做 run ownership 校验和 append，不会读取或伪造 UI 状态。Runner 当前没有 Guest GUI adapter、真实 Kdenlive 内部状态采集或完整双 Actor scheduler；计划字段不等同于实机运行。

## 运行命令

```bash
python -m oscombo.collab.timeline_and_assets prepare /tmp/codesk-tla/run-001 --run-id tla-run-001
python -m oscombo.collab.timeline_and_assets configure /tmp/codesk-tla/run-001 --condition collaborative_shared
python -m oscombo.collab.timeline_and_assets collab-serve --run-root /tmp/codesk-tla/run-001 --port 8767
python -m oscombo.collab.timeline_and_assets evaluate /tmp/codesk-tla/run-001
python -m oscombo.collab.timeline_and_assets reset /tmp/codesk-tla/run-001 --run-id tla-run-001
python -m pytest -q tests/test_timeline_and_assets.py
```

`prepare` 创建初始工程，不生成 gold 产物。正式 Agent 编辑须走 Kdenlive GUI；`fixture.write_gold_artifacts` 只在离线测试中生成正确 oracle positive control。
