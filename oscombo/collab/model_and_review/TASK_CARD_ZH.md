# CoDesk Model-and-Review（CDD-MAR-001）Task Card

版本：0.1.0（真实 Blender initial/Gold fixture 已生成；Guest GUI 仍待验证）

## 场景与共同产物

用户需要完成一盏桌灯的几何修改、尺寸/灯泡间隙核验和产品展示布光。输入是一份可由 Blender 打开的桌灯半成品工程；唯一最终产物是可重新打开的 `StudioLamp_Final.blend`。A 负责灯罩几何，B 负责几何审查及相机/灯光。两者有共同产品目标，但可分时操作，不要求同时编辑，也不通过隐藏规格或固定消息轮次制造协作。

这个任务增加此前案例未覆盖的 Blender 应用内部状态：活动对象、选中集、Object/Edit Mode、活动工作区/区域、3D 视口变换和活动相机。共享桌面条件允许 B 在 A 留下的实时 Blender 会话中查看场景并继续操作；B 的视口或选择变更也会成为 A 恢复任务时所见的当前应用上下文。发生状态暴露不等于发生干扰，必须分别记录暴露、误操作/修复、最终结果。

## 初始场景

`StudioLamp_Review` 场景有且只有九个命名对象：`Lamp_Base`、`Lamp_Stem`、`Lamp_Shade`、`Lamp_Bulb`、`Studio_Floor`、`Camera_Main`、`Key_Light`、`Fill_Light`、`Rim_Light`。材质名分别为 `Mat_Porcelain`、`Mat_Brass`、`Mat_Deep_Green`、`Mat_Warm_Glass`、`Mat_Floor`。初始灯罩偏小，初始相机焦距与三盏灯能量未达到目标；其余结构已有且需要保护。完整 gold 仅存放在 evaluator 侧。

仓库包含使用 Blender `bpy` 建立真实初始/Gold 工程的脚本 `blender/build_fixture.py`。`fixtures/initial.blend` 是部分完成的公开起始工程；`fixtures/private/gold.blend` 是 evaluator 私有正确工程，不能提供给 Actor。两份文件均由 Blender 5.2.2 LTS 后台生成、重新打开并通过场景快照检查。Blender GUI/Guest 操作尚未验证。

## 两个角色

**A — Geometry owner**：完整阅读任务资料；只调整 `Lamp_Shade` 外部尺寸为 `1.50 × 1.50 × 0.80 m`、中心位置 `(0, 0, 2.50 m)`；保持灯罩原形和材质；核验灯泡在灯罩内的间隙；不改其他部件或相机/灯光；保存检查点。A 可查看所有对象和规格，也可在需要时向 B 发消息/附件。B 提出具体几何问题时，A 可修订并再次保存。

**B — Reviewer and presentation owner**：完整阅读任务资料并检查 A 的最新灯罩几何；独立核验灯泡间隙、基座/灯杆/灯泡完整性；设置相机及三盏灯到下列目标；保存最终工程。B 可提出具体问题请 A 修订，也可附上审查记录。B 不改灯罩或其他几何。

这是一种责任划分，不是访问权限隔离。Blender 本身没有在本实现中启用对象级写入 ACL；越权更改由独立 Oracle 检出。消息数量和交接时点不固定，结果评估不会把发消息本身计作协作成功。

## Gold Answer

| 对象 | Gold 状态 |
| --- | --- |
| `Lamp_Shade` | Mesh；location `(0,0,2.50)`；dimensions `(1.50,1.50,0.80)`；`Mat_Deep_Green`；内侧底/顶半径 `0.56/0.70 m`，外侧半径 `0.60/0.75 m` |
| `Lamp_Bulb` | Mesh；location `(0,0,2.35)`；dimensions `(0.24,0.24,0.24)`；`Mat_Warm_Glass` |
| 灯泡净空 | 在灯泡中心高度计算内壁径向净空至少 `0.40 m`；灯泡到开口/内缘竖向净空至少 `0.10 m` |
| `Camera_Main` | location `(4.20,-6.00,3.20)`；50 mm；镜头方向对准 `(0,0,1.45)` |
| `Key_Light` | AREA；location `(3,-4,5)`；450 W；size 4 m；色值 `(1,.92,.82)` |
| `Fill_Light` | AREA；location `(-3,-1,3)`；160 W；size 3 m；色值 `(.72,.82,1)` |
| `Rim_Light` | AREA；location `(0,3,4)`；320 W；size 2 m；色值 `(1,.72,.48)` |
| 非目标保护 | `Lamp_Base`、`Lamp_Stem`、`Lamp_Bulb`、`Studio_Floor` 的名称、类型、位置、尺寸和材质必须与 Gold 完全一致；对象集合和五个材质颜色也必须精确匹配 |

公差仅用于浮点序列化误差（默认 `1e-4`；相机方向 dot `1e-3`），不放宽结构、尺寸或非目标保护。灯泡净空由 Blender 网格顶点提取的灯罩内外半径剖面与灯泡尺寸计算。

## 对照条件与因果边界

| 条件 | 桌面 | 场景/文件后端 | 消息与评分 |
| --- | --- | --- | --- |
| Single-Agent | 一个桌面，S 完成两角色工作 | 一个 episode 级 canonical 版本化 `.blend` artifact store | 与协作条件相同的消息接口、输入资料及结构 Oracle；S 的总预算等于 A+B 预算之和 |
| Collaborative-Isolated | A、B 各自独立 Blender 桌面 | 与 Shared 相同的单一 canonical artifact store、初始文件哈希、版本和保存服务；每轮读取最新已提交 revision | 同一 ProtocolStore、角色目标、各自预算、保存租约和 Oracle |
| Collaborative-Shared | 一个 Blender 桌面，A/B 在动作边界交接控制权 | 与 Isolated 完全相同的 canonical artifact store、初始哈希、版本规则 | 同上 |

每次保存都需要当前 Actor 的单写租约并提交 revision；交接前保存，后继 Actor 读取同一最新 revision。MA-ID 与 MA-SD 都不允许同时写同一 `.blend`。MA-ID 的独立桌面各自加载最新已保存 revision；MA-SD 的单会话保留活动对象、选择、模式和视口等易失应用状态。实验只比较桌面会话状态是否共享，不比较文件副本、后端、媒体或数据同步差异。同步版本号或文件哈希不匹配的 episode 标为基础设施无效。

共享桌面可能带来的便利是，B 能直接审阅 A 当前打开的对象和视口，交接时不必另起 Blender 会话；风险是 B 接手时当前对象、模式和视口可能与其目标不一致，或 B 的观察/相机修改影响 A 恢复时的上下文。它们是可观察机会，不是必然失败。

## Oracle 与过程指标

独立 Oracle 使用 `bpy` 读取最终 `.blend`，归一化为 `fixtures/scene_snapshot.schema.json`，然后核验对象集合、几何变换、材料、灯泡净空、相机、灯光、非目标对象保护及场景身份。`fixtures/gold_state.json` 为私有 Gold，不能提供给 Actor。正例必须全部通过；负例包括灯罩尺寸/剖面偏差、灯泡净空不足、错焦距、错灯功率、删改底座/灯杆/灯泡、增加/删除对象、材料改变和镜头未对准。

过程数据单独报告：消息与附件、Actor 的最终产物贡献、状态变化暴露、目标对象之外的修改、保存 revision、是否发现问题及修复。窗口/视口变化本身不算干扰。只有动作目标与操作前后状态日志共同支持时才归因到错误活动对象、错误模式或错误视口；最终错误也可能是普通建模错误。

## 实现/验证状态

- 离线规格、Gold 快照 Oracle、正负例契约测试、条件配置、消息绑定和只读状态采样接口：见实现报告。
- 真实 `.blend` initial/Gold 生成、后台重开和结构 Oracle：已验证；保存重开、正式 run reset：见实现报告。
- Blender GUI 可操作性、Guest 兼容性、Single、MA-ID、MA-SD、自然暴露/干扰/恢复：Pending；本轮没有启动 GUI、Guest、QEMU 或模型。
