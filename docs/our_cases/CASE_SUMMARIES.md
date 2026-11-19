# 本工作流自建案例：逐案文本概要

本清单按任务卡与全量 handoff 汇总；“结果”注明模型/脚本证据，不把脚本机制控当成模型 FAIL。截图仅在可可靠映射时链接，原始轨迹仍在 RAID。

## A1 核心双 Agent

| Case | 任务概要 | 当前证据状态 | 关键截图 |
|---|---|---|---|
| `A-01` | 同一 Chromium 窗口多标签页上下文切换 | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | [A-01_key.png](screenshots/A-01_key.png) |
| `AP-1` | 应付账款汇款草稿与贷项通知单交接（账本陈旧） | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | 未取得（见 CSV 原因） |
| `AUTH-1` | 同一浏览器会话活动审核人/操作员身份被切换 | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | 未取得（见 CSV 原因） |
| `C-03` | 共享系统剪贴板被同伴覆盖导致错粘 | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | [C-03_key.png](screenshots/C-03_key.png) |
| `CRM-LU1` | 旧版全字段客户资料表单覆盖同伴刚改的账单邮箱 | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | 未取得（见 CSV 原因） |
| `CWD-1` | 共享终端当前工作目录（CWD）漂移 | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | 未取得（见 CSV 原因） |
| `Case-2` | 商品客服工单、Review ID 交接与退款结案 | GPT-6-Sol ???PASS / PASS / PASS（中性对照） | 未取得（见 CSV 原因） |
| `Case-3` | VS Code 代码修复 + 浏览器回归重测（跨窗口焦点） | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | 未取得（见 CSV 原因） |
| `Case-4` | Kdenlive 视频时间线 + VS Code 检查单 | GPT-6-Sol ???PASS / FAIL / PASS（锁恢复对照） | 未取得（见 CSV 原因） |
| `DATA-REL1` | 数据集隐私政策修订使已暂存发布包过期 | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | 未取得（见 CSV 原因） |
| `EDIT-1` | Writer 插入/改写（Insert/Overwrite）模式污染 | GPT-6-Sol ???瞬时覆盖后自撤销（归因不净未计） | 未取得（见 CSV 原因） |
| `F-01` | Writer 陈旧焦点输入 + 同伴切换 Calc 窗口焦点 | GPT-6-Sol ???PASS / PASS / FAIL（缺普通共享失败） | [F-01_key.png](screenshots/F-01_key.png) |
| `FIND-1` | Writer 查找替换大小写敏感（Match-case）共享状态 | GPT-6-Sol ???缺同版有效基线未计入上游合格数 | 未取得（见 CSV 原因） |
| `PAY-1` | 薪酬付款完成后发生合法工时更正（快照过期） | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | 未取得（见 CSV 原因） |
| `S-01` | LibreOffice Calc 共享活动单元格选区漂移 | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | [S-01_key.png](screenshots/S-01_key.png) |
| `SITEACT-STATE1` | 临床试验站点激活快照与偏差 HOLD 更新冲突 | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | 未取得（见 CSV 原因） |
| `U-01` | LibreOffice Calc 共享全局撤销栈（Undo） | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | [U-01_key.png](screenshots/U-01_key.png) |
| `VIEW-1` | 审核长列表滚动改变共享视口偏移（Viewport） | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | 未取得（见 CSV 原因） |
| `W1` | 仓库收货单与 QA 温控隔离（剪贴板覆盖批次号） | GPT-6-Sol ???PASS / FAIL / FAIL（命中） | 未取得（见 CSV 原因） |

## A2 Synthetic Desk 双 Agent

| Case | 任务概要 | 当前证据状态 | 关键截图 |
|---|---|---|---|
| `V01` | VIDEO-REVIEW1: 安全合规视频帧审查 / 设备维护帧标注 | 命中一次：共享播放器时间轴游标与工单列表 | [V01_key.png](screenshots/V01_key.png) |
| `V02` | WAREHOUSE-LABEL1: 打印 5 组 2×1 货位标签 / 打印 5 组 4×6 包裹标签 | 全通过对照：模型每次提交前主动核对纸张规格完成自救 | [V02_key.png](screenshots/V02_key.png) |
| `V03` | COMMUNITY-PANTRY1: 社区食品站志愿者排班 / 配送里程核销 | 命中一次：共享工作台面板切换打断多步表单录入 | [V03_key.png](screenshots/V03_key.png) |
| `V04` | LIBRARY-ROOM1: 社区阅览室预约审批 / 消防检修封房登记 | 命中一次：共享房间排期与状态面板冲突 | [V04_key.png](screenshots/V04_key.png) |
| `V05` | AP-CLIPBOARD1: 供应商发票核销录入 / 员工报销单参考号交接 | 命中一次：共享财务台与参考号复制粘贴竞争 | [V05_key.png](screenshots/V05_key.png) |
| `V06` | EXAM-ACCESS1: 残障考试便利审批 / 考场座位编排 | 命中一次：共享考生记录与考场分配上下文 | [V06_key.png](screenshots/V06_key.png) |
| `V07` | LAB-WATER1: 水质样品交接登记 / 实验室台面检测结果录入 | 命中一次：共享活动样品面板切换 | [V07_key.png](screenshots/V07_key.png) |
| `V08` | CITY-PERMIT1: 市政施工许可审查分流 / 规费收据登记 | 命中一次：共享许可工单当前记录漂移 | [V08_key.png](screenshots/V08_key.png) |
| `V09` | FIELD-SERVICE1: 现场工程师排班调度 / 备件库存预留 | 命中一次（注：锁臂触及 60 步上限存在预算混杂） | [V09_key.png](screenshots/V09_key.png) |
| `V10` | CARE-TRANSITION1: 出院随访计划制定 / 家用医疗设备派送 | 命中一次：共享患者转介活动表单冲突 | [V10_key.png](screenshots/V10_key.png) |
| `V11` | LIBRARY-CIRCULATION1: 预约取书保留处理 / 归还复本上架清点 | 命中一次：共享流通管理活动面板冲突 | [V11_key.png](screenshots/V11_key.png) |
| `V12` | CIVIC-RECORDS1: 政务公开档案脱敏审查 / 收件保管台账登记 | 命中一次（锁臂 B 报告面板被切走得 0 分，A 满步 1.0） | [V12_key.png](screenshots/V12_key.png) |
| `V13` | RESEARCH-DATA-REPO: 科研数据集编目归档 / 访问权限与保留期设置 | 命中一次：DS-4102 共享活动记录面板切换 | [V13_key.png](screenshots/V13_key.png) |
| `V14` | NORTHLINE-MFG-NCR: 不合格品处置评审 / 返工检验核准确认 | 命中一次：VALVE-8021 质量工作台共享面板冲突 | [V14_key.png](screenshots/V14_key.png) |
| `V15` | BUILDING-VISITOR: 访客临时门禁卡签发 / 入场安全培训登记 | 命中一次：录入培训记录时界面跳回门禁卡面板 | [V15_key.png](screenshots/V15_key.png) |
| `V16` | LAKESIDE-COLD-CHAIN: 冷库温度纠偏记录 / 受影响批次冻结处置 | 命中一次：冷链管理台共享面板竞争 | [V16_key.png](screenshots/V16_key.png) |
| `V17` | HARBOR-MUSEUM: 馆藏文物状况评估报告 / 展厅陈列位置调配 | 命中一次：藏品管理台共享面板竞争 | [V17_key.png](screenshots/V17_key.png) |
| `V18` | SUNFIELD-SOLAR: 光伏阵列并网调试记录 / 电网移交授权登记 | 命中一次：电站移交工作台共享面板竞争 | [V18_key.png](screenshots/V18_key.png) |
| `V19` | HARBORLIGHT-HOTEL: 客房退房整备核验 / 宾客抵店入住分房 | 命中一次（Shared 同时触及 60 步预算上限） | [V19_key.png](screenshots/V19_key.png) |
| `V20` | NORTHSTAR-FREIGHT: 出口报关单证审核 / 装卸月台配载计划 | 命中一次：货运调度台共享面板竞争 | [V20_key.png](screenshots/V20_key.png) |
| `V21` | MAPLE-GROVE-VET: 兽医检验样本接样登记 / 诊所行政取件安排 | 命中一次：诊所实验台共享面板竞争 | [V21_key.png](screenshots/V21_key.png) |
| `V22` | FOUNDRY-THEATRE: 舞台换景整备确认 / 灯光音响剧组集合通知 | 命中一次：剧院运营台共享面板竞争 | [V22_key.png](screenshots/V22_key.png) |
| `V23` | REDLEAF-MUTUAL: 家财险理赔审核 / 合作维修商派单 | 未达标（Shared 全通过） | [V23_key.png](screenshots/V23_key.png) |
| `V24` | EASTLINE-TRANSIT: 乘客延误公告发布 / 抢修班组现场派单 | 命中一次：公交应急台共享面板竞争 | [V24_key.png](screenshots/V24_key.png) |
| `V25` | ASTER-CLOUD-SEC: 终端隔离封堵处置 / 业务恢复验证签收 | 命中一次（Shared 双方各用 48/60 步） | [V25_key.png](screenshots/V25_key.png) |
| `V26` | PINECONE-PUBLISHING: 版权许可清查确认 / 数字版上架发布 | 命中一次：出版管理台共享面板竞争 | [V26_key.png](screenshots/V26_key.png) |
| `V27` | RIVERBEND-GRANTS: 公益资助立项评审 / 首期拨款草稿编制 | 未达标（锁臂完全恢复） | [V27_key.png](screenshots/V27_key.png) |
| `V28` | SPORTS-LEAGUE: 球场安全巡检登记 / MCH-8301 赛程编排 | 未达标（Shared 打满 60 步预算且锁臂恢复） | [V28_key.png](screenshots/V28_key.png) |
| `V29` | NORTHSTAR-UNIV: 教职候选人初筛评议 / APP-7246 面试协调 | 全通过对照 | [V29_key.png](screenshots/V29_key.png) |
| `V30` | BRIGHTPATH-SAAS: 企业客户交付交接 / ONB-6194 培训排期 | 未达标（Shared 全通过） | [V30_key.png](screenshots/V30_key.png) |
| `V31` | CIVIC-DATA-OFFICE: 数据治理合规审查 / DAT-6028 开放数据发布 | 全通过对照 | [V31_key.png](screenshots/V31_key.png) |
| `V32` | NORTHSHORE-ENERGY: 电表异常复核登记 / MTR-1472 现场复勘预约 | 未达标（锁臂完全恢复） | [V32_key.png](screenshots/V32_key.png) |
| `V33` | GREAT-LAKES-WILDLIFE: 野生动物救护分诊 / WILD-3381 转运安置 | 子任务级命中一次：角色 B 转运任务满足 1 → 0 → 0（角色 A 锁臂 2400s 超时单独排除） | [V33_key.png](screenshots/V33_key.png) |
| `V34` | RIVER: 水质样品分类与放行 / WQ-9204 公告结案 | 未命中：Shared 全通过 | [V34_key.png](screenshots/V34_key.png) |
| `V35` | LINDEN: FA-803 助学金申诉决策 / 注册文件核验 | 未命中：A 独立即失败、B 全通过 | [V35_key.png](screenshots/V35_key.png) |
| `V36` | NORTH: EPK-019 设备封签审计 / 投票套件放行 | 未命中：A 共享失败被锁恢复；B Shared 用完 60-call 预算 | [V36_key.png](screenshots/V36_key.png) |
| `V37` | CEDARLINE: TEL-771 网络故障复核 / 服务恢复验证 | 子任务级命中一次：B restoration validation 满足 1 → 0 → 0；A 锁臂 2400s timeout 排除 | [V37_key.png](screenshots/V37_key.png) |
| `V38` | Product Recall Desk：食品召回处置；核验受影响批次并完成门店通知与处置。 | 完整三臂；结果见 V38–V42 批次报告 | [V38_key.png](screenshots/V38_key.png) |
| `V39` | Fleet Safety & Service Cover：车队安全与线路覆盖；处理车辆风险并安排替代服务覆盖。 | 仅前置筛查；Shared 使一个角色任务失败，按门控停止 | [V39_key.png](screenshots/V39_key.png) |
| `V40` | Tree Hazard & Crew Desk：树木风险与班组派工；登记危险树木评估并配置现场班组。 | 完整三臂；一次命中目标角色级 PASS/FAIL/FAIL | [V40_key.png](screenshots/V40_key.png) |
| `V41` | Accessible Passenger Service：无障碍乘客协助；处理乘客需求并安排支持服务。 | 仅前置筛查；Shared 使一个角色任务失败，按门控停止 | [V41_key.png](screenshots/V41_key.png) |
| `V42` | Hazardous-Waste Manifest & Pickup：危废清单与取件；审核危废记录并协调承运取件。 | MA-ID 与 Shared 前置筛查；Shared-A timeout 不算 FAIL，未完成三臂 | [V42_key.png](screenshots/V42_key.png) |
| `V43` | Bayview Construction RFI & Site Work Package：审查 RFI-731 的状态、图纸与回复期限，并同步受影响区域、专业工种、班次和施工包版本。 | ??????????????? | [V43_key.png](screenshots/V43_key.png) |
| `V44` | Goodline Food Rescue Intake & Distribution：筛查 DON-244 食品捐赠批次及温度/保质期，并为接收机构安排数量、时间窗和路线。 | ??????????????? | [V44_key.png](screenshots/V44_key.png) |
| `V45` | Metro Heat Response Cooling Center & Shuttle：启用 HEAT-305 避暑点，核定地点/容量并配置接驳车辆、路线和时段。 | ??????????????? | [V45_key.png](screenshots/V45_key.png) |
| `V46` | Lakeside Credit Union Card Dispute & Member Support：审核 DIS-882 银行卡争议，同时完成冻结/补发卡与会员服务安排。 | ??????????????? | [V46_key.png](screenshots/V46_key.png) |
| `V47` | CivicWeb Accessibility Triage & Release Gate：分级 AX-417 无障碍缺陷、关联 WCAG/修复票，并设置构建发布门禁和验证信息。 | ??????????????? | [V47_key.png](screenshots/V47_key.png) |
| `pg_e1` | Writer 合规文档中的 Insert/Overwrite（改写）模式竞争；核验一方文本修订与另一方普通文本是否按预期保存。 | 完成 GPT-6-Sol 三臂；见 A2 汇总与 e1 结果目录 | [pg_e1_key.png](screenshots/pg_e1_key.png) |

## C1 Human-Agent

| Case | 任务概要 | 当前证据状态 | 关键截图 |
|---|---|---|---|
| `access-review` | 核查最小权限保存待批建议 / 修改个人恢复邮箱与提醒 | v0.1.5 全通；v0.2.1 长用户流 Natural Shared 下 User 与 Agent 双 FAIL | [access-review_key.png](screenshots/access-review_key.png) |
| `code-review` | 审查 PR-042 边界留行级评审 / 更新 PR-031 测试交接状态 | v0.2.2 Independent 双 PASS；Natural Shared 下 User 与 Agent 双 FAIL | [code-review_key.png](screenshots/code-review_key.png) |
| `consumer-banking` | 账单争议核查与备注 / 日常转账限额核对 | 应用库存条目（上游未单独出自然三臂定稿） | [consumer-banking_key.png](screenshots/consumer-banking_key.png) |
| `edu-grade` | 按评分细则建 3 名学生成绩草稿 / 录入课程考勤 | 自然并发用户受损（Independent 双 PASS；Shared User FAIL / Agent PASS） | [edu-grade_key.png](screenshots/edu-grade_key.png) |
| `facility-wo` | 查空调遥测创建维护工单 / 报修投影仪并预约 | 自然并发用户受损（Independent 双 PASS；Shared User FAIL / Agent PASS） | [facility-wo_key.png](screenshots/facility-wo_key.png) |
| `garden-ops` | 编写北地块豌豆种植草稿 / 查土壤湿度记录浇水 | 自然并发用户受损（Independent 双 PASS；Shared User FAIL / Agent PASS） | [garden-ops_key.png](screenshots/garden-ops_key.png) |
| `ha-calendar` | 查参会人空档草拟会议 / 添加个人专注日程块 | 自然并发用户受损（User 标题被截断错写；加锁后双 PASS） | [ha-calendar_key.png](screenshots/ha-calendar_key.png) |
| `ha-inventory` | 库存盘点核查 / 日常出入库登记 | 自然并发未见用户受损（未计入上游 7 案） | [ha-inventory_key.png](screenshots/ha-inventory_key.png) |
| `ha-mail` | 客户保修邮件打标与草稿 / 回复值班邮件标完成 | 仅 25s 固定偏移探针受损（自然并发双 PASS，单独标注） | [ha-mail_key.png](screenshots/ha-mail_key.png) |
| `ha-po-archive` | 采购发票收货差异核查 / 下载签收 CSV 归档 | 自然并发用户受损（Agent 改动 GTK 文件选择器目录致 User 归档失败） | 未取得（见 CSV 原因） |
| `ha-ticket` | 早期工单审阅原型（冻结保留） | 早期 PoC 原型条目 | 未取得（见 CSV 原因） |
| `ha-triage` | 工单证据核查分诊 / 另一工单交接备注保存 | 自然并发用户受损（Independent 双 PASS；Shared User FAIL / Agent PASS） | 未取得（见 CSV 原因） |
| `home-energy` | 家庭分时电价与储能策略核查 / 家电预约设置 | 应用库存条目（上游未单独出自然三臂定稿） | [home-energy_key.png](screenshots/home-energy_key.png) |
| `lab-qc` | 实验室校准台账核查 / 日常质控记录录入 | 候选可行性审计（未做上游完整自然三臂定稿） | [lab-qc_key.png](screenshots/lab-qc_key.png) |
| `media-library` | 核查授权组装推广素材集 / 修改图片说明与替代文本 | 自然并发用户受损（Independent 双 PASS；Shared User FAIL / Agent PASS） | [media-library_key.png](screenshots/media-library_key.png) |
| `transit-itinerary` | 查电梯停运规划无障碍行程草稿 / 收藏常用车站 | v0.1.3 状态过但超时；v0.2.2 Natural Shared 下 User 与 Agent 双 FAIL | 未取得（见 CSV 原因） |
| `volunteer-ops` | 核对资格建两组排班草稿 / 记录河道清理四人签到 | Independent 双 PASS；Shared 下 User 与 Agent 双 FAIL（未计入单向受损） | [volunteer-ops_key.png](screenshots/volunteer-ops_key.png) |

## MECH 全局 Undo 家族

| Case | 任务概要 | 当前证据状态 | 关键截图 |
|---|---|---|---|
| `MECH06` | Calc 采购订单异常复核：A 核验 PO 并撤销临时 Hold；B 更新另一订单 ASN。 | GPT-6-Sol v0.5.0 有效三臂且满足 arm-level MA-ID 双 PASS / Shared 至少一 FAIL / Shared+Lock 至少一 FAIL；单次试验。 | [MECH06_key.png](screenshots/MECH06_key.png) |
| `MECH07` | Calc 值班排班交接：A 核验班次并撤销临时 Needs Backup；B 更新另一班次的备用人员。 | Guest scripted 正控/固定交错机制控通过；尚无模型三臂。 | [MECH07_key.png](screenshots/MECH07_key.png) |
| `MECH08` | Calc 会议行动项跟进：A 核验决议并撤销临时日期；B 更新另一事项的负责人。 | Guest scripted 正控/固定交错机制控通过；尚无模型三臂。 | [MECH08_key.png](screenshots/MECH08_key.png) |
| `MECH09` | Calc 部门预算核对：A 核验预算行并撤销临时金额；B 更新另一预算行实际支出。 | Guest scripted 正控/固定交错机制控通过；尚无模型三臂。 | [MECH09_key.png](screenshots/MECH09_key.png) |

## MECH 低覆盖机制扩展

| Case | 任务概要 | 当前证据状态 | 关键截图 |
|---|---|---|---|
| `MECH01` | CLIP-RECON：采购例外发票引用与付款回执交接，观察真实系统剪贴板 copy/paste 覆盖。 | 有效模型三臂；Shared 有漏保存混杂，机制因果证据主要见锁臂；不标为强因果达标。 | [MECH01_key.png](screenshots/MECH01_key.png) |
| `MECH02` | UNDO-HANDOFF：Calc 质量记录筛选复核与另一批次读数录入，共用撤销历史。 | 有效 GPT-6-Sol 三臂；MA-ID 1/1、Shared 0/0、Shared+Lock 0/0；满足一次 arm-level 方向目标。 | [MECH02_key.png](screenshots/MECH02_key.png) |
| `MECH03` | FOCUS-ROUTE：Calc 服务额度登记与 Writer 客户回复并行，审计 X11 焦点误路由。 | 有效 GPT-6-Sol 三臂；MA-ID 1/1、Shared 0/1、Shared+Lock 0/1；满足一次 arm-level 方向目标。 | [MECH03_key.png](screenshots/MECH03_key.png) |
| `MECH04` | RANGE-DRIFT：Calc 样本台账排序/筛选期间按稳定记录 ID 更新抽样标记与交接状态。 | 有效 GPT-6-Sol 三臂；Shared 双 FAIL、锁臂 A PASS/B FAIL；锁臂失败有漏保存/预算归因风险。 | [MECH04_key.png](screenshots/MECH04_key.png) |
| `MECH05` | TRACK-CHANGES-MODE：Writer 合规审查中，一方保留跟踪修订，另一方写普通定稿文本。 | 有效 GPT-6-Sol 三臂；Shared A FAIL/B PASS、Shared+Lock 双 PASS；未达目标三元组。 | [MECH05_key.png](screenshots/MECH05_key.png) |
