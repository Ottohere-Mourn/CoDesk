# -*- coding: utf-8 -*-
"""精选 23 题中文元信息、多维分类体系与字段翻译字典。"""
from __future__ import annotations

import re
from typing import Any

BATCH_META: dict[str, dict[str, str]] = {
    "Curated-8": {
        "label": "Curated-8 · 经典精选 8 题",
        "short": "Curated-8",
        "color": "#2563eb",
        "desc": "从既有双智能体桌面套件精选的 8 道高质量基准，涵盖 6 题多驱桌面竞争与 2 题高难工程/并购耦合任务。",
    },
    "AW-v1 (2h uncapped)": {
        "label": "AW-v1 · 真实工作站 Top-5",
        "short": "AW-v1",
        "color": "#0d9488",
        "desc": "真实 Linux 专业桌面软件（Chromium/GIMP/Inkscape/Qt5/LibreOffice/FreeCAD）2 小时无步数上限压测 Top-5。",
    },
    "NF-v1 (Authentic Rework)": {
        "label": "NF-v1 · 前沿原语重构 Top-5",
        "short": "NF-v1",
        "color": "#7c3aed",
        "desc": "彻底去除玩具界面后，围绕 XKB 键盘布局、BroadcastChannel、UNO 裂脑、共享 Python 内核与 Blender 3.4 重构的 5 道正交原语题。",
    },
    "NF2 (2h uncapped)": {
        "label": "NF2 · 前沿原生桌面二期 Top-5",
        "short": "NF2",
        "color": "#d97706",
        "desc": "聚焦 Qt5 Assistant、Blender VSE、FreeCAD 装配、QGIS 3.22 SpatiaLite 与铁路 ETCS Qt5 工具链的 5 道二期前沿题。",
    },
}

MECHANISM_META: dict[str, dict[str, str]] = {
    "office_uno": {
        "label": "单实例办公文档与 UNO 裂脑",
        "short": "办公/UNO 裂脑",
        "color": "#2563eb",
        "desc": "双角色共享单一 soffice.bin 进程、已打开的 Calc/Writer 工作簿与跨表耦合约束，极易产生保存覆盖与公式裂脑。",
    },
    "browser_viewport": {
        "label": "浏览器视口、断点与同源状态争用",
        "short": "浏览器/视口争用",
        "color": "#0891b2",
        "desc": "共用 Chromium 实例、窗口尺寸/全屏独占、同源 BroadcastChannel 状态同步或无剧透前端多态交互探索。",
    },
    "qt_x11_input": {
        "label": "Qt 原生工具链、XKB 布局与焦点争用",
        "short": "Qt/XKB/焦点争用",
        "color": "#7c3aed",
        "desc": "争夺 X11 活动窗口焦点、系统级 XKB 德英键盘布局、Qt5 Designer/Linguist/Assistant 原生控件与输入路由。",
    },
    "cad_3d_media": {
        "label": "CAD / 3D / 图像与非线性剪辑专业软件",
        "short": "CAD/3D/图形媒体",
        "color": "#d97706",
        "desc": "共享 FreeCAD B-Rep 实体装配、Blender 3.4 3D/VSE、单实例 GIMP 2.10 与 Inkscape 矢量画布及物理参数耦合。",
    },
    "kernel_gis_schedule": {
        "label": "共享计算内核、空间数据库与排程耦合",
        "short": "内核/GIS/排程耦合",
        "color": "#059669",
        "desc": "共享实时 Python 计算内核、QGIS SpatiaLite 地理数据库或本地邮件日程系统，叠加跨角色容量/预算上限。",
    },
}

DOMAIN_META: dict[str, dict[str, str]] = {
    "medical_bio": {
        "label": "医疗临床与生物医药",
        "short": "医疗与生医",
        "color": "#e11d48",
    },
    "finance_enterprise": {
        "label": "金融、法务与企业运营",
        "short": "金融与企业运营",
        "color": "#2563eb",
    },
    "aero_rail_energy": {
        "label": "航空航天、轨交与能源电网",
        "short": "航电/轨交/能源",
        "color": "#d97706",
    },
    "hardware_research_media": {
        "label": "硬件工程、科研与创意媒体",
        "short": "工程/科研/媒体",
        "color": "#0d9488",
    },
}

MODE_ZH: dict[str, str] = {
    "isolated": "隔离单跑基线 (Isolated)",
    "seq_ab": "顺序单跑基线 (Seq A→B)",
    "shared": "共享桌面并发 (Shared)",
}

MODEL_ZH: dict[str, str] = {
    "gpt-6.1-sol": "GPT-6.1-Sol (high)",
    "gpt-6-astra": "GPT-6-Astra (high)",
}

TOOL_ZH: dict[str, str] = {
    "guest_bash": "终端命令 (guest_bash)",
    "get_state": "读取桌面窗口状态",
    "get_screenshot": "截取桌面画面",
    "get_ax_state_and_screenshot": "读取无障碍树 + 截屏",
    "get_ax_state": "读取无障碍树 (AT-SPI2)",
    "screenshot": "截取桌面画面",
    "click": "鼠标点击",
    "double_click": "鼠标双击",
    "right_click": "鼠标右键",
    "click_and_type": "点击并输入文本",
    "move": "移动指针",
    "mouse_move": "移动指针",
    "drag": "鼠标拖拽",
    "scroll": "滚轮滚动",
    "type_text": "键盘输入文本",
    "key": "发送快捷键/按键",
    "press_key": "按下按键",
    "hotkey": "组合快捷键",
    "wait": "等待暂停",
    "focus_window": "切换/聚焦窗口",
    "activate_window": "激活窗口",
    "clipboard_get": "读取剪贴板",
    "clipboard_set": "写入剪贴板",
}

CASE_CATALOG_ZH: dict[str, dict[str, Any]] = {
    "RBS3-04": {
        "title_zh": "重症 ICU 单位切换、16 床室速波形监护与单实例 LibreOffice 液体台账耦合",
        "summary_zh": "两名重症医护智能体在同一桌面协作/争用：既需在无 CDP 门户与 QPainter 16 床室速波形监护仪中完成临床读数，又必须共同编辑已打开的单实例 LibreOffice Calc 液体负荷台账与 Writer 交班文档。",
        "mechanism": "office_uno",
        "domain_cat": "medical_bio",
        "software_stack": ["LibreOffice Calc", "LibreOffice Writer", "Chromium", "QPainter 监护仪"],
        "contention_zh": "单实例 soffice.bin（Calc + Writer）保存裂脑、无 CDP 门户单位全局切换冲突与 16 床液体总负荷跨表耦合。",
        "roles_zh": {
            "vasopressor_pharmacist": {
                "name_zh": "血管活性药师",
                "brief_zh": "识别 16 床室速（VTach）告警波形，计算去甲肾上腺素/血管加压素滴定剂量与载体液体量并写入台账。",
            },
            "ventilator_renal_lead": {
                "name_zh": "呼吸机与肾脏病主治",
                "brief_zh": "完成 16 床 ARDS 俯卧位分诊、肾脏补液量测算与交班文档更新，并受全床液体上限与单位切换约束。",
            },
        },
    },
    "RBS3-05": {
        "title_zh": "嵌入式总线/VRM 门户、红外 PCB 热点图、实时网关修复与耦合 TDP BOM",
        "summary_zh": "固件工程师与热功耗工程师并行排障：一方面通过红外热点渲染与实时 :19515 CAN-FD 守护进程修复固件，另一方面共同维护已打开的 LibreOffice Calc 8 分区热降额与 TDP 物料表。",
        "mechanism": "office_uno",
        "domain_cat": "hardware_research_media",
        "software_stack": ["LibreOffice Calc", "Chromium", "QPainter IRCam", "CAN-FD 守护进程"],
        "contention_zh": "无 CDP 总线/VRM 门户状态切换、单实例 Calc 热功耗 BOM 并发写入与整板 TDP 预算双向耦合。",
        "roles_zh": {
            "protocol_firmware_eng": {
                "name_zh": "协议固件工程师",
                "brief_zh": "定位并修复 :19515 CAN-FD 网关守护进程故障，核定 ASIC 功耗包络与通信遥测。",
            },
            "thermal_power_eng": {
                "name_zh": "热设计与电源工程师",
                "brief_zh": "读取 8 分区红外 PCB 热点，完成 VRM 热降额计算并同步更新共享热功耗 BOM 表。",
            },
        },
    },
    "RBS3-02": {
        "title_zh": "单例 Chromium 4 断点 FinOps 像素巡检 vs. 8 场景全屏无遮挡遥测录屏",
        "summary_zh": "前端 QA 需在单例 Chromium（:9222）下反复调整 4 种响应式视口断点并做像素验证；另一名遥测导演需在 1920×1080 无遮挡全屏下连续采集 8 个 OrbitMesh 实时动态场景。",
        "mechanism": "browser_viewport",
        "domain_cat": "finance_enterprise",
        "software_stack": ["Chromium (:9222)", "FinOps Web", "OrbitMesh 全屏应用"],
        "contention_zh": "1920×1080 屏幕全屏独占与 4 断点窗口缩放的直接视觉遮挡冲突，叠加单例浏览器焦点抢占。",
        "roles_zh": {
            "finops_viewport_auditor": {
                "name_zh": "FinOps 响应式视口审计员",
                "brief_zh": "对 GridFlow FinOps 进行 4 断点布局、弹窗与像素级视觉回归验证。",
            },
            "orbit_reel_director": {
                "name_zh": "OrbitMesh 遥测录屏导演",
                "brief_zh": "确保 1920×1080 全屏无任何遮挡，按序捕获 8 场景动态遥测演示序列。",
            },
        },
    },
    "RBS2-06": {
        "title_zh": "MailDesk 视觉冲突热力图与 RFC-5545 日程排期 vs. Calc 供应商 SLA 合同",
        "summary_zh": "教务排程员需通过桌面 MailDesk 客户端查看不可用热力图并编排 12 场学位答辩的 .ics 日程；合同工程师则需对账 SQLite 邮件库并完成 10 份供应商 SLA 增补与 Calc 经费包络表。",
        "mechanism": "kernel_gis_schedule",
        "domain_cat": "hardware_research_media",
        "software_stack": ["MailDesk 客户端", "LibreOffice Calc", "SQLite", "RFC-5545 .ics"],
        "contention_zh": "共享 MailDesk 桌面客户端/SQLite 数据源与设施经费上限，在桌面焦点与 Calc 预算汇总处形成双向制约。",
        "roles_zh": {
            "defense_scheduler": {
                "name_zh": "答辩日程排程员",
                "brief_zh": "依据 MailDesk 视觉冲突热力图，无冲突安排 12 场答辩房间与费率并输出标准 .ics。",
            },
            "contract_automation_eng": {
                "name_zh": "合同自动化工程师",
                "brief_zh": "核对 10 份供应商 SLA 增补条款并在共享 Calc 台账中闭合设施资助经费包络。",
            },
        },
    },
    "RBS-06": {
        "title_zh": "CiteVault 文献去重、BibTeX 清理与单实例 Writer+Calc 荟萃分析",
        "summary_zh": "系统综述编辑需在 CiteVault SQLite 与 BibTeX 库中去重并修订 20 篇文献及 Writer 文稿；生物统计师需在单实例 Calc 中完成 16 项研究的逆方差固定效应 Meta 分析并与文稿口径对齐。",
        "mechanism": "office_uno",
        "domain_cat": "hardware_research_media",
        "software_stack": ["CiteVault SQLite", "LibreOffice Writer", "LibreOffice Calc", "BibTeX"],
        "contention_zh": "单实例 soffice.bin 同时挂载 Writer 论文与 Calc 统计工作簿，且文献纳入集合变化直接联动效应量。",
        "roles_zh": {
            "bib_manuscript_editor": {
                "name_zh": "文献与手稿编辑",
                "brief_zh": "清理 20 篇研究记录的 CiteVault SQLite 与 BibTeX 条目，并更新 Writer 综述手稿。",
            },
            "evidence_quant_analyst": {
                "name_zh": "生物统计荟萃分析师",
                "brief_zh": "在 Calc 中计算 16 项研究的逆方差固定效应合并值、异质性指标并核对手稿数据。",
            },
        },
    },
    "RBS3-01": {
        "title_zh": "无剧透 5 界面复刻：自动隐藏 F10 浮层、三页签偏好设置与音频/抓包工作室",
        "summary_zh": "两名逆向工程智能体看不到目标源码，必须在共享桌面上交替操作正在运行的 PacketForge 与 SpectrumPad 两款桌面软件，通过点击、F10 浮层与多页签探索全部交互细节并完整复刻。",
        "mechanism": "qt_x11_input",
        "domain_cat": "hardware_research_media",
        "software_stack": ["PacketForge 桌面端", "SpectrumPad 桌面端", "PyQt5/QPainter", "X11 浮层"],
        "contention_zh": "F10 弹出浮层一失去焦点即自动消失，双智能体在无剧透探索期间频繁抢夺窗口焦点导致浮层闭合。",
        "roles_zh": {
            "packetforge_recreator": {
                "name_zh": "PacketForge 复刻工程师",
                "brief_zh": "交互式探索 PacketForge 全部面板、F10 浮层与三页签设置并零剧透复刻应用。",
            },
            "spectrumpad_recreator": {
                "name_zh": "SpectrumPad 复刻工程师",
                "brief_zh": "交互式探索 SpectrumPad 音频 DSP 界面、EQ 曲线与偏好配置并完成等价复刻。",
            },
        },
    },
    "EC-01": {
        "title_zh": "多实体并购财务尽调数据室、在线 Calc 裂脑与杠杆契约测算",
        "summary_zh": "并购交易团队中的 QoE 负责人与税务资金负责人共用同一套数据室与已打开的 LibreOffice Calc 并购模型，分别完成 EBITDA 调整、循环信贷额度测算以及税务赔偿、外汇解约与非受限现金核算。",
        "mechanism": "office_uno",
        "domain_cat": "finance_enterprise",
        "software_stack": ["LibreOffice Calc", "SQLite ERP 总账", "PDF/图像附件", "共享数据室"],
        "contention_zh": "双角色并发编辑同一已打开的 Calc 并购估值模型，且 EBITDA 与净负债/现金口径共同决定杠杆契约边界。",
        "roles_zh": {
            "qoe_ebitda_lead": {
                "name_zh": "QoE 与 EBITDA 尽调负责人",
                "brief_zh": "汇总多实体总账完成盈利质量（QoE）调整、EBITDA 合并及循环信贷额度测算。",
            },
            "tax_treasury_lead": {
                "name_zh": "税务与司库负责人",
                "brief_zh": "核定交割税务敞口、外汇解约成本、非受限现金及税务赔偿附注并回填模型。",
            },
        },
    },
    "EC-03": {
        "title_zh": "1U 钣金机箱 FreeCAD B-Rep 建模、Inkscape 印前制版与热/EMI 预紧力耦合",
        "summary_zh": "结构热工程师与电磁兼容印前工程师协同交付 1U 通信机箱 Rev-C 改版：分别在 FreeCAD 实体模型与 Inkscape 面板丝印中加工通风孔、后部 I/O 隔板与导电衬垫，并满足散热与屏蔽预紧耦合指标。",
        "mechanism": "cad_3d_media",
        "domain_cat": "hardware_research_media",
        "software_stack": ["FreeCAD 0.20", "Inkscape 1.2", "LibreOffice Calc", "工业工程图纸"],
        "contention_zh": "共享 FreeCAD 机箱装配体与热/EMI 耦合规格表，并发修改孔位与衬垫尺寸易触发几何冲突或文件覆盖。",
        "roles_zh": {
            "mech_thermal_eng": {
                "name_zh": "结构与热设计工程师",
                "brief_zh": "完成 1U 顶盖散热开孔 B-Rep 加工建模与整机热流道排程核算。",
            },
            "emi_prepress_eng": {
                "name_zh": "EMC 屏蔽与丝印印前工程师",
                "brief_zh": "完成背板 I/O 隔板加工、导电衬垫预紧力核算与前面板 Inkscape 印前丝印制版。",
            },
        },
    },
    "AW-12": {
        "title_zh": "无剧透 8 状态 Chronos ERP 模块化 SPA 复刻：履约台 vs. 产能与容灾规划",
        "summary_zh": "两名资深前端工程师在不知源码的情况下，共同探索浏览器中运行的 Chronos ERP 8 状态单页应用，分别摸清订单履约弹窗/筛选与产能容灾抽屉/暗黑模式，并模块化重构复刻。",
        "mechanism": "browser_viewport",
        "domain_cat": "finance_enterprise",
        "software_stack": ["Chromium", "Chronos ERP SPA", "HTML5/CSS3/JS"],
        "contention_zh": "同一运行中的 Chromium SPA 会话内，双方并发点击标签页、筛选气泡、抽屉和深浅主题互相改变界面状态。",
        "roles_zh": {
            "orders_ui_eng": {
                "name_zh": "订单与 SLA 前端工程师",
                "brief_zh": "完整探索并复刻 Orders & SLA 模块的全部筛选胶囊、弹出层与顶部快捷弹窗。",
            },
            "capacity_ui_eng": {
                "name_zh": "产能与容灾前端工程师",
                "brief_zh": "完整探索并复刻 Capacity & Failover 模块的子页签、区域条动作、侧滑预案抽屉与暗色切换。",
            },
        },
    },
    "AW-14": {
        "title_zh": "单实例 GIMP 4 图层隐藏与 600×400 缩放 + 在线 Inkscape 学术海报制作",
        "summary_zh": "荧光显微图像分析师与凝胶电泳分析师在同一台工作站上使用单实例 GIMP 2.10 处理多层科研原图，并将成品嵌入共同编辑的 Inkscape 研讨会矢量海报（Panel A / Panel B）及 72 行 SQLite 实验库。",
        "mechanism": "cad_3d_media",
        "domain_cat": "hardware_research_media",
        "software_stack": ["GIMP 2.10", "Inkscape 1.2", "Chromium", "SQLite (72 行)"],
        "contention_zh": "GIMP 2.10 单实例多文档与 Inkscape 共享 poster_layout.svg 画布并发编辑，焦点与导出状态相互干扰。",
        "roles_zh": {
            "microscopy_img_analyst": {
                "name_zh": "荧光显微图像分析师",
                "brief_zh": "在 GIMP 中处理多层显微图像、隐藏指定图层并缩放到 600×400，更新海报 Panel A。",
            },
            "gel_blot_analyst": {
                "name_zh": "凝胶电泳印迹分析师",
                "brief_zh": "在 GIMP 中处理凝胶电泳图层与裁剪缩放，核对 SQLite 数据并更新海报 Panel B。",
            },
        },
    },
    "AW-15": {
        "title_zh": "纯 GUI Qt5 Designer 血透仪控制台设计 & Qt5 Linguist 8 条 ICU 德语本地化",
        "summary_zh": "医疗器械 HMI 安全工程师与临床本地化工程师并发操作打开在桌面上的 Qt5 Designer（.ui）与 Qt5 Linguist（.ts），落实 IEC 60601-2-16 血透安全上下限、8 条德语翻译、编译 .qm 并核验跨膜压数据。",
        "mechanism": "qt_x11_input",
        "domain_cat": "medical_bio",
        "software_stack": ["Qt5 Designer", "Qt5 Linguist", "lrelease", "Chromium", "SQLite"],
        "contention_zh": "纯 GUI 桌面窗口密集输入与快捷键操作极易触发焦点抢占与误路由按键（实测单局多达 40+ 次误路由）。",
        "roles_zh": {
            "dialysis_ui_eng": {
                "name_zh": "血透仪 Qt5 HMI 安全工程师",
                "brief_zh": "在 Qt5 Designer 中配置符合 IEC 60601-2-16 的微调框安全边界与急停触控约束。",
            },
            "dialysis_l10n_eng": {
                "name_zh": "血透临床本地化与 TMP 工程师",
                "brief_zh": "在 Qt5 Linguist 中完成全部 8 条德语医疗术语翻译、发布 .qm 并校核跨膜压指标。",
            },
        },
    },
    "AW-19": {
        "title_zh": "超大规模数据中心 Capex 核算与主机托管 MSA 合同在线 Calc/Writer 交割",
        "summary_zh": "数据中心资本开支财务官与商业法务顾问共用 56 行 SQLite 采购/租约台账以及在线打开的 LibreOffice Calc 与 Writer，协同完成 32 行硬件 PO 估值、24 批托管租约 SLA 敞口与合同红线修订。",
        "mechanism": "office_uno",
        "domain_cat": "finance_enterprise",
        "software_stack": ["LibreOffice Calc", "LibreOffice Writer", "Chromium", "SQLite (56 行)"],
        "contention_zh": "同一 LibreOffice 实例内同时打开 Calc 汇总表与 Writer MSA 协议，双方并发保存与 Deal_Rollup 跨表引用高度耦合。",
        "roles_zh": {
            "dc_capex_controller": {
                "name_zh": "数据中心 Capex 财务控制官",
                "brief_zh": "基于 32 行采购单台账核算 FY26 硬件资本开支，更新 Hardware_Capex 与 Deal_Rollup。",
            },
            "msa_commercial_counsel": {
                "name_zh": "MSA 商业与托管租约法务",
                "brief_zh": "测算第 2 年托管租约与 SLA 违约敞口，并在 Writer 中完成 MSA 商业条款红线修订。",
            },
        },
    },
    "AW-20": {
        "title_zh": "ISO 13485 医用监护仪发布：FreeCAD 前后壳 + GIMP 面板覆膜 + 悬臂平衡 DHR",
        "summary_zh": "前框工程师与后部 VESA 镁合金底盘工程师并行推进医用监护仪量产发布：共同修改 FreeCAD 机壳装配体、使用单实例 GIMP 制作前后覆膜丝印，并在 Calc 中联合满足悬臂质心平衡与 DHR 签核。",
        "mechanism": "cad_3d_media",
        "domain_cat": "medical_bio",
        "software_stack": ["FreeCAD 0.20", "GIMP 2.10", "LibreOffice Calc", "Chromium"],
        "contention_zh": "三软件联合作战：共享 .FCStd 装配模型、单实例 GIMP 覆膜编辑以及 Calc 悬臂力矩平衡签核表。",
        "roles_zh": {
            "front_bezel_overlay_eng": {
                "name_zh": "前框与面板覆膜工程师",
                "brief_zh": "完成 FrontBezel 3D 开孔建模与显示屏量产图形覆膜，提交前部重量参数。",
            },
            "rear_vesa_chassis_eng": {
                "name_zh": "后部 VESA 底盘与铭牌工程师",
                "brief_zh": "完成 RearVesaPlate 3D 加工开孔与后部合规铭牌，联合闭合悬臂平衡 DHR 签核。",
            },
        },
    },
    "NF-01": {
        "title_zh": "DACH 双语工作站 XKB 键盘布局争用（DE-QWERTZ vs. US-QWERTY）：Writer 排版与 Calc 营收对账",
        "summary_zh": "德奥瑞法务本地化负责人需在德语 QWERTZ 布局下编辑 Writer 法定声明并校验 OpenType DIN-1450 字体；EMEA 营收建模师需在美式 QWERTY 布局下于 Calc 中输入公式完成多币种 SaaS 营收对账。",
        "mechanism": "qt_x11_input",
        "domain_cat": "finance_enterprise",
        "software_stack": ["X11 XKB 布局", "LibreOffice Writer", "LibreOffice Calc", "fontTools", "SQLite"],
        "contention_zh": "全局 XKB 键盘布局（de QWERTZ 与 us QWERTY）在 Z/Y 及标点符号键位冲突，且共用单实例 LibreOffice。",
        "roles_zh": {
            "dach_legal_localization_lead": {
                "name_zh": "DACH 法务本地化与字体负责人",
                "brief_zh": "编制德奥瑞法定 Impressum 文档、校验 DIN-1450 字体字形指标并打包合规发布件。",
            },
            "emea_revops_modeler": {
                "name_zh": "EMEA 多币种营收运营建模师",
                "brief_zh": "结合 SQLite 订阅流水完成 Q3/Q4 多币种营收对账并在 Calc 中落盘公式与汇总。",
            },
        },
    },
    "NF-05": {
        "title_zh": "同源 BroadcastChannel 与响应式视口争用：420 笔成交微结构 QA vs. 18 节点行情 DAG 回放",
        "summary_zh": "量化执行研究员与行情数据链路 SRE 共用同源 Chromium 交易工作台，一方执行 420 笔子单滑点审计与窄屏订单抽屉 QA，另一方排查 18 节点 5 阶段行情 DAG 分区倾斜，期间同源 BroadcastChannel 会互相广播污染状态。",
        "mechanism": "browser_viewport",
        "domain_cat": "finance_enterprise",
        "software_stack": ["Chromium", "BroadcastChannel API", "量化执行工作台", "行情 DAG 看板"],
        "contention_zh": "浏览器同源 BroadcastChannel 跨页签广播状态污染，叠加响应式窄屏/宽屏视口尺寸争夺。",
        "roles_zh": {
            "execution_quant_researcher": {
                "name_zh": "量化执行微结构研究员",
                "brief_zh": "审计 420 笔欧股子单执行滑点（IS）与限价项圈合规，并完成响应式订单抽屉 QA。",
            },
            "market_data_lineage_sre": {
                "name_zh": "行情血缘与管线 SRE",
                "brief_zh": "在 /etl-lineage 看板定位 18 节点行情 DAG 回补链路与分区倾斜根因并输出报告。",
            },
        },
    },
    "NF-11": {
        "title_zh": "生物制剂冷链超温 LIMS 与 LibreOffice UNO 裂脑：432 样本阿伦尼乌斯 MKT vs. 4 航段干冰验证",
        "summary_zh": "生物制剂稳定性 QA 与低温包装热工程师围绕单抗批次 mAb-Lot-994A 超温事件协作：分别在 LIMS 与已打开的 Calc/Writer 中完成 432 个多探头样本的阿伦尼乌斯平均动力学温度（MKT）放行评估，以及 4 航段 IATA PI-954 干冰升华验证。",
        "mechanism": "office_uno",
        "domain_cat": "medical_bio",
        "software_stack": ["LibreOffice Calc", "LibreOffice Writer", "冷链 LIMS 门户", "UNO API"],
        "contention_zh": "共享在线 LibreOffice UNO 文档与磁盘文件双写裂脑，且批次放行结论与 4 航段保温裕度强耦合。",
        "roles_zh": {
            "biologics_stability_qa": {
                "name_zh": "生物制剂稳定性 QA",
                "brief_zh": "计算 432 样本多探头阿伦尼乌斯 MKT 与稳定性衰减，出具 mAb-Lot-994A GMP 放行判定。",
            },
            "packaging_thermal_eng": {
                "name_zh": "低温包装热工程师",
                "brief_zh": "按 IATA PI-954 核算 BSL-FRA-ANC-KIX 四航段干冰升华消耗与加注量资格。",
            },
        },
    },
    "NF-13": {
        "title_zh": "共享实时 Python 内核（NotebookHub）与 Calc 冷库货架排程：生鲜价格弹性 vs. (s, S) 补货耦合",
        "summary_zh": "需求弹性数据科学家与冷链补货工程师共用同一个活跃的 NotebookHub Python 内核与在线 Calc 货架排程表：前者拟合生鲜 BOGO 促销弹性并分配冷藏位，后者执行 98% 服务水平 (s, S) 冷冻补货并受总氨制冷负荷耦合约束。",
        "mechanism": "kernel_gis_schedule",
        "domain_cat": "finance_enterprise",
        "software_stack": ["NotebookHub 共享内核", "LibreOffice Calc", "Python/Pandas", "冷库排程表"],
        "contention_zh": "共享单 Python 内存内核（全局变量、工作目录与执行队列竞争）叠加 Calc 冷藏/冷冻库容联合上限。",
        "roles_zh": {
            "demand_elasticity_ds": {
                "name_zh": "需求弹性数据科学家",
                "brief_zh": "在共享 NotebookHub 内核中估算生鲜促销价格弹性并规划冷藏货位分配。",
            },
            "cold_storage_replenisher": {
                "name_zh": "冷链库存补货规划师",
                "brief_zh": "在共享内核中插补缺货数据并测算 98% 服务水平 (s, S) 冷冻托盘位补货方案。",
            },
        },
    },
    "NF-14": {
        "title_zh": "在线 Blender 3.4 手术机器人工作站 GUI 与 Writer DHF：13 网格避障运动学 vs. 内窥镜光学热约束",
        "summary_zh": "机器人运动学工程师与内窥镜光学热工程师共享桌面运行的 Blender 3.4 3D 手术场景与 Writer 设计历史文档（DHF）：一方调整双机械臂消除 13 个器官网格碰撞与视线遮挡，另一方标定内窥镜工作距、Cycles 渲染与 LED 温升上限。",
        "mechanism": "cad_3d_media",
        "domain_cat": "medical_bio",
        "software_stack": ["Blender 3.4 GUI", "Cycles 渲染", "LibreOffice Writer", "DHF 文档"],
        "contention_zh": "并发修改同一已打开的 Blender 3.4 .blend 场景与相机视角，机械臂位姿调整直接影响光学无遮挡渲染。",
        "roles_zh": {
            "robotics_kinematics_eng": {
                "name_zh": "手术机器人运动学工程师",
                "brief_zh": "解算左右抓钳臂姿态消除 13 器官网格碰撞与视线干扰，并验证双极电凝占空比。",
            },
            "endoscope_optics_eng": {
                "name_zh": "内窥镜光学与热工程师",
                "brief_zh": "标定内窥镜相机工作距、输出靶标视野 Cycles 渲染图并核验 IEC 温升安全上限。",
            },
        },
    },
    "NF2-05": {
        "title_zh": "原生 Qt5 Assistant 多手册过滤争用与在线 Calc：ARINC-429 总线解码 vs. 飞控增益裕度",
        "summary_zh": "航电总线工程师与飞控增益分析师共用桌面上打开的原生 Qt5 Assistant 航电手册浏览器（.qhc）与 Calc 核验表：双方必须各自切换不同手册过滤视图查表，分别完成 32 位 ARINC-429 帧解码奇偶校验与 MIL-F-9490D 增益/相位裕度闭合。",
        "mechanism": "qt_x11_input",
        "domain_cat": "aero_rail_energy",
        "software_stack": ["Qt5 Assistant (.qhc)", "LibreOffice Calc", "ARINC-429 数据", "DO-254 手册"],
        "contention_zh": "单实例 Qt5 Assistant 文档过滤器全局切换冲突，叠加单实例 Calc 航电验证工作簿并发写入。",
        "roles_zh": {
            "arinc429_bus_engineer": {
                "name_zh": "ARINC-429 总线工程师",
                "brief_zh": "切换至总线 ICD 手册过滤视图，完成 32 位 ARINC-429 帧字段解码与奇偶校验审计。",
            },
            "flight_gain_analyst": {
                "name_zh": "飞控增益裕度分析师",
                "brief_zh": "切换至 MIL-F-9490D 飞控手册过滤视图，完成波特图增益与相位裕度闭合验算。",
            },
        },
    },
    "NF2-11": {
        "title_zh": "在线 Blender 3.4 视频序列编辑器（VSE）与 FFmpeg/SoX 混音：纪录片剪辑 vs. 1800 帧播控上限",
        "summary_zh": "非编剪辑师与广播混音师协同交付纪录片成片：前者在桌面打开的 Blender 3.4 VSE 时间线中完成镜头剪辑与 EDL 核对，后者用 FFmpeg/SoX 执行 -16.0 dBFS EBU-R128 对白母带处理与赞助商导视插入，并严守 1800 帧总时长上限。",
        "mechanism": "cad_3d_media",
        "domain_cat": "hardware_research_media",
        "software_stack": ["Blender 3.4 VSE", "FFmpeg", "SoX", "LibreOffice Calc"],
        "contention_zh": "共享在线 Blender VSE 时间线 .blend 文件与 1800 帧刚性播控总时长，剪辑与音轨插入直接互斥。",
        "roles_zh": {
            "vse_assembly_editor": {
                "name_zh": "VSE 纪录片剪辑师",
                "brief_zh": "在 Blender 3.4 VSE 中完成画面轨剪辑、转场拼装与 EDL 帧级时长核查。",
            },
            "broadcast_re_recording_mixer": {
                "name_zh": "广播终混与母带工程师",
                "brief_zh": "执行对白音轨 -16.0 dBFS 响度标准化、赞助商垫片对位与总帧数校验。",
            },
        },
    },
    "NF2-12": {
        "title_zh": "在线 FreeCAD 0.20 实体装配与 Calc：6U 立方星主承力结构 vs. 星敏感器质量重心包络",
        "summary_zh": "卫星结构 CAD 工程师与载荷光学热工程师共同操作桌面运行的 FreeCAD 0.20 6U 立方星装配体（.FCStd）与 Calc 质量特性表：前者减重挖槽优化主结构刚度，后者修剪星敏遮光罩与散热板，联合将整星质量与质心锁入发射包络。",
        "mechanism": "kernel_gis_schedule",
        "domain_cat": "aero_rail_energy",
        "software_stack": ["FreeCAD 0.20 (.FCStd)", "LibreOffice Calc", "航天质量特性表"],
        "contention_zh": "共享 FreeCAD 装配体文件与整星质量/质心（CG）耦合包络约束，单边改动即影响另一方包络裕度。",
        "roles_zh": {
            "spacecraft_bus_cad_eng": {
                "name_zh": "卫星平台结构 CAD 工程师",
                "brief_zh": "对 Al-7075 主舱壳体执行减重掏槽建模并校验模态刚度指标。",
            },
            "payload_optics_thermal_eng": {
                "name_zh": "载荷光学与热控工程师",
                "brief_zh": "修整星敏感器遮光罩几何尺寸与辐射散热平衡，闭合整星质量重心包络。",
            },
        },
    },
    "NF2-13": {
        "title_zh": "在线 QGIS 3.22 共享 SpatiaLite 地理库与 Calc：社区光伏 vs. 公交 EV 充电站 N-1 变电站容量上限",
        "summary_zh": "社区光伏 GIS 工程师与公交超充规划师共享 QGIS 3.22 中打开的 SpatiaLite 空间数据库图层与 Calc 馈线分配表：分别筛查光伏并网地块与 EV 超充谐波负荷，并共同服从变电站 N-1 MVA 容量硬上限。",
        "mechanism": "kernel_gis_schedule",
        "domain_cat": "aero_rail_energy",
        "software_stack": ["QGIS 3.22", "SpatiaLite", "LibreOffice Calc", "GDAL/OGR"],
        "contention_zh": "QGIS 共享 SpatiaLite 空间图层写锁冲突，叠加同一变电站 N-1 MVA 配额的跨角色总容量博弈。",
        "roles_zh": {
            "community_solar_gis_eng": {
                "name_zh": "社区光伏 GIS 工程师",
                "brief_zh": "在 QGIS 共享并网队列图层筛查 SOLAR_PV 地块空间合规性并分配馈线容量。",
            },
            "ev_depot_charging_planner": {
                "name_zh": "公交 EV 超充场站规划师",
                "brief_zh": "筛查 EV_DCFC 场站并核定谐波 MVA 容量，与光伏份额共同严守 N-1 变电站上限。",
            },
        },
    },
    "NF2-15": {
        "title_zh": "在线 Qt5 Designer 与 Qt5 Linguist 联动：欧洲铁路 ETCS 驾驶台人机界面与德法双语安全词条",
        "summary_zh": "轨道交通 HMI 人因工程师与铁路安全本地化负责人并发操作 Qt5 Designer（etcs_cab_dmi.ui）与 Qt5 Linguist（.ts/.qm）：前者按 ERA 规范调整 DMI 布局并验算紧急制动曲线，后者完成 8 条德/法安全词条翻译、编译并检验控件文本截断。",
        "mechanism": "qt_x11_input",
        "domain_cat": "aero_rail_energy",
        "software_stack": ["Qt5 Designer (.ui)", "Qt5 Linguist (.ts)", "lrelease", "Chromium", "SQLite"],
        "contention_zh": "Qt5 Designer 与 Linguist 双原生窗口高频焦点抢占，且控件几何宽度直接决定德/法安全告警文本是否越界。",
        "roles_zh": {
            "rail_hmi_ergonomics_eng": {
                "name_zh": "铁路 HMI 人因工程师",
                "brief_zh": "按 ERA ETCS 标准调整驾驶台 .ui 布局尺寸，并结合 SQLite 验算紧急制动物理曲线。",
            },
            "rail_safety_l10n_lead": {
                "name_zh": "铁路安全本地化负责人",
                "brief_zh": "补全全部 8 条未完成德语/法语安全词条翻译、编译 .qm 并验证界面文本贴合度。",
            },
        },
    },
}


def translate_tool_name(tool_name: str) -> str:
    if not tool_name:
        return "未知工具"
    short = tool_name.split(".")[-1]
    if short in TOOL_ZH:
        return TOOL_ZH[short]
    return tool_name


def translate_check_key(key: str) -> str:
    """将英文判分检查键名转换为易读中文提示。"""
    if not key:
        return ""
    tokens = {
        "exists": "文件存在",
        "json": "JSON 校验",
        "csv": "CSV 校验",
        "xlsx": "表格校验",
        "ods": "表格校验",
        "odt": "文档校验",
        "docx": "文档校验",
        "svg": "矢量图校验",
        "png": "图像校验",
        "pdf": "PDF 校验",
        "sqlite": "数据库校验",
        "sql": "数据库校验",
        "ics": "日程文件校验",
        "bib": "BibTeX 校验",
        "ui": "Qt UI 校验",
        "ts": "翻译源文件校验",
        "qm": "编译词条校验",
        "fcstd": "FreeCAD 模型校验",
        "blend": "Blender 工程校验",
        "dirty": "脏状态检查",
        "clean": "干净保存检查",
        "saved": "已保存检查",
        "formula": "公式校验",
        "formulas": "公式校验",
        "sum": "汇总数值",
        "total": "总计核对",
        "budget": "预算包络",
        "cap": "上限约束",
        "margin": "裕度检查",
        "parity": "奇偶校验",
        "render": "渲染输出",
        "clearance": "避障间隙",
        "thermal": "热学指标",
        "mkt": "阿伦尼乌斯 MKT",
        "dry": "干冰校验",
        "ice": "冷链校验",
        "l10n": "本地化词条",
        "layout": "布局校验",
        "viewport": "视口断点",
        "modal": "弹窗交互",
        "pixel": "像素对比",
        "gui": "GUI 交互状态",
        "live": "在线状态",
        "lock": "锁状态检查",
        "joint": "双角色联合约束",
        "coupled": "耦合约束",
        "coupling": "耦合约束",
        "reconcile": "对账一致",
        "audit": "审计通过",
        "pass": "通过",
    }
    clean = re.sub(r"^[abj]_", "", key)
    parts = [p for p in clean.split("_") if p]
    zh_hits = [tokens[p.lower()] for p in parts if p.lower() in tokens]
    if zh_hits:
        dedup = list(dict.fromkeys(zh_hits))
        return " · ".join(dedup[:3])
    return clean.replace("_", " ")
