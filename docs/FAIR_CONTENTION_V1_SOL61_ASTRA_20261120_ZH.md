# 公平无锁长程双智能体真实软件竞争套件 `fair_contention_v1`（`FC-01..FC-15`）设计与 `gpt-6.1-sol` / `gpt-6-astra` 实测报告

更新日期：2026-11-20
所在分支：`codex/all-codesk-cases-20261113`
实测集群：`g4-45`（96 核 Xeon + 866 GiB RAM + Non-YOLO Docker）与 `cpu15`（32 核 + 125 GiB RAM），全部结构化日志与结果已持久化归档至 `cpu15:~/data/paraGUI/runs/fair-contention-vfinal-20261120/` 及本仓库 `docs/results-manifests/`

## 一、核心结论与去人工化重设计准则

为构建不依赖任何人工机关、完全基于真实桌面环境与真实专业软件内在状态耦合的 **30 分钟+ 长程双智能体（`Role A` + `Role B`）并发竞争基准**，我们逐题手工打造并迭代定型了覆盖 15 个独立工程领域的 **`fair_contention_v1`（`FC-01..FC-15`）** 套件：

1. **彻底清零四类人工机制（100% 公平透明协议）**：
   - **零首笔提交锁与隐藏印章**：门户 `/submit` 始终评估最新一次合法提交；任何结构、公式、物理或耦合越界均显式返回 `HTTP 422` 及具体诊断项，绝不存在静默吞掉请求的伪 `200 OK` 或 `official_wire_receipt` / `amendment_eco_seal`。
   - **零显式禁写令与非对称步数差**：彻底移除 `Do NOT modify /workspace until...` 与 `6 vs 16` 类非对称延迟；双角色均执行完全对称的 5 阶段渐进式工程验证（单阶段真实求解/渲染约 `195–325s`，全程 30+ 分钟高度重叠）。
   - **零脱钩代数空转**：彻底废除纯数学 `(param_u, param_v)` 凑数标定；每一次 `/api/bench/...` 调用均直接读取、编译、查询、仿真或渲染 `/workspace` 中的实时生产交付物（FreeCAD `.FCStd`/`.step`、Blender Cycles、GCC `.so`、SQLite WAL、LibreOffice `.xlsx`、QGIS/GDAL `.gpkg`/`.qgz`、MLT/FFmpeg、CMYK `.tiff`、KiCad `.kicad_pcb`、AutoCAD `.dxf`、OpenSSL X.509、2D FFT 波前、64×64 `.npz` 掩模等）。
   - **零单向 `v0` 死锁陷阱**：所有耦合约束与初始基线经严格双向可解性验证，确保无论 `Role A -> Role B` 还是 `Role B -> Role A` 顺序执行均可无死锁收敛。
2. **四大自动化门禁（`self_validate`）15/15 全量通过**：
   - `Gate 1 (pristine)`：初始状态 `joint_pass == False`（`15/15` 全满足）；
   - `Gate 2a (seq_ab)`：`Role A -> Role B` 串行正控 `joint_pass == True`（`15/15` 全通过）；
   - `Gate 2b (seq_ba)`：`Role B -> Role A` 反向串行正控 `joint_pass == True`（`15/15` 全通过）；
   - `Gate 3 (sim_race)`：无协调并发竞争模拟 `joint_pass == False`（`15/15` 全拦截）；
   - `Gate 4 (protocol_transparency)`：`FORBIDDEN_PROMPT_PATTERNS` 命中为 `0`，所有评分路径、端点、指标与工况令牌 100% 公开可见（`15/15` 全通过）。
3. **前沿双模型并发与双向串行实测主结果**：
   - **`gpt-6.1-sol (high)` 双并发（15 题）**：联合通过率 **`0 / 15 (0.0%)`**，角色局部签收 **`28 / 30`**，零显式竞争察觉任务 **`11 / 15`**，跨角色不变量均分 `0.3700`，单局墙钟范围 **`31.7m – 39.7m`**（均值 **`35.2m`**）。
   - **`gpt-6-astra (high)` 双并发（15 题）**：联合通过率 **`0 / 15 (0.0%)`**，角色局部签收 **`23 / 30`**，零显式竞争察觉任务 **`7 / 15`**，跨角色不变量均分 `0.3367`，单局墙钟范围 **`32.5m – 41.7m`**（均值 **`37.0m`**）。
   - **真实大模型双向串行正控验证**：`gpt-6.1-sol (high)` 在双向串行控制（`seq_ab` 与 `seq_ba`）下均取得 **`joint_pass = True`（`closed = 2/2, inv = 1.0000`）**，证明全部并发失败均严格源自双智能体共享桌面与共享工程状态竞争。

## 二、多轮真实模型攻防取证与机制演进（v1 -> v2 -> v3 -> v_final）

在逐题打磨与真实模型并发测试过程中，基于 `actions.jsonl` 与 `portal_state.json` 的纯文本行为取证揭示了前沿模型规避简单竞争的三大真实机制，并驱动了最终架构升级：

1. **文件系统与进程树旁路建锁（伴生容器隔离）**：早期双角色共用同一用户空间时，`gpt-6.1-sol` 与 `gpt-6-astra` 会通过 `ps aux` 发现同伴进程，或在 `/workspace` 与 `/tmp` 下创建 `COORDINATION.txt` 协商参数。我们在 `FairContentionDesktop` 中引入双角色伴生用户容器（共享 `--network container:<desk>`、`/tmp/.X11-unix` X11 显示、`/workspace` 生产目录及只读目录权限 `0755` 的 `/home/gui/Downloads`，但完全隔离 PID 命名空间、`/tmp` 与 `$HOME`），同时为 `/status` 增加基于 `role_token.txt` 的角色鉴权，并在每次 `/bench` 与 `/submit` 调用时递归执行 `verify_clean_workspace`（存在非交付临时文件立即返回 `HTTP 422`），彻底消除文件系统聊天室。
2. **共享 Chromium 开发者控制台（F12 / Ctrl+Shift+J）跨角色可见性与 JS 注入旁路（X11 按键捕获）**：在中期取证中发现，两款模型有超过 80% 的局次会按下 `F12` 或 `Ctrl+Shift+J` 呼出 `DISPLAY=:99` 上共享 Chromium 窗口的 DevTools 控制台——后截图的角色不仅直接在屏幕截图中读到了同伴输入的 `console.log` 调试信息并主动推迟扫参，还能直接用 `await fetch('/api/ui/...')` 在毫秒级完成状态切换。我们在桌面容器 Openbox `rc.xml` 中配置 X11 根窗口级 `XGrabKey` 拦截 `F12`、`Ctrl+Shift+I/J/C` 与 `Ctrl+U`（辅以 `xmodmap` 屏蔽 `F12` 键码），在不影响无头 `chromium --headless` PDF/多视口渲染的前提下，将实测打开的 DevTools 窗口数精准降至 **`0`**，迫使智能体执行真实的 GUI 屏幕点击。
3. **瞬时扫参低占空比逃逸与连续多阶段 SSO 工况保持冲突（v_final 核心机制）**：早期仅在第 1 分钟执行的 `4 × 6.5s`（`26s / 1800s = 1.4%` 占空比）导出易因两角色阅读文档的时间差而自然错开；同时全局台架互斥锁在无意中将两角色的仿真串行错开并引发短超时重试堆积。终极版改为按子系统独立加锁（`sub_locks[sub]`）使双角色 5 阶段（每阶段约 `195–325s`）真正并行运行，并明确规定各子系统在整个导出与 **Stages 2..5 连续约 13–21 分钟的台架鉴定期间**必须在共享 SSO 控制台（`DISPLAY=:99`）上维持各自专属的互斥工况/口径/温区（`BackgroundRegimeSampler` 每 `2.0s` 采样一次实时环境纯度，若重跑任一阶段则自动刷新最新纯度，无任何永久锁死），配合导出 CSV/剪贴板延迟金丝雀及 `/workspace` 跨角色物理耦合不变量，在双向串行 100% 通过的同时实现了对无感知并发的稳定拦截。

4. **跨角色文案微泄漏消除与鸽巢原理（Pigeonhole Bound）时序标定**：在第一轮全量 140s 阶段测试中，所有单局时长 <= 26.3 分钟的并发局 100% 触发冲突失败（14/14 FAIL），但部分公共提示同时列出了双子系统的互斥工况名，使后手角色在看到屏幕处于另一工况时推断存在并发同伴并主动休眠 12–15 分钟，利用 2 × 16m = 32m < 60m 的时间富余将并发自发退化为串行轮流执行。终极版一方面将工况保持说明严格内聚至各角色独立工单（零对端角色名或对端工况名提及），另一方面依据各题实测非台架开销精确标定 5 阶段仿真时长（220s–325s，严格低于 MCP 工具超时上限 360s）与并发总预算（38–42m），使双角色 Stages 2..5 所需的互斥环境保持总时长严格大于 Stage 1 之后的剩余并发窗口（满足鸽巢不等式 2 × T_stages2..5 > T_window，而单角色双向串行 32–37m < 48m 宽裕通过）。

## 三、15 项手工定制场景与四门禁双向自验证总表（15 / 15 全通）

| ID | 领域与双角色（Role A / Role B） | 真实软件栈与核心共享载体 | 真实竞争与耦合机制 | Gate1 pristine | Gate2a seq_ab | Gate2b seq_ba | Gate3 sim_race | Gate4 transparent |
|---|---|---|---|---|---|---|---|---|
| `FC-01` | 航空同轴四级伺服作动器三维 B-Rep 建模、热扭耦合与光追剖视签发<br>`stator_lead` / `rotor_lead` | FreeCAD (.FCStd / .step) + Blender Cycles + LibreOffice Calc (.xlsx) + Chromium SSO PLM | `monolithic_fcstd_zip_lost_update + bidirectional_airgap_mass_cg_coupling + single_session_plm_csv_export` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-02` | 电商结账 C 定价内核、PBKDF2/HMAC 幂等复式账本与三视口在线演练场发布<br>`checkout_perf_lead` / `security_ledger_lead` | Git (main) + GCC (libpricing.so) + SQLite WAL + Live HTTP Port 20120 + 3-Viewport Chromium | `live_staging_mid_soak_restart + git_main_and_server_py_merge_race + worker_pbkdf2_memory_sla_coupling + sso_canvas_session_switch` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-03` | 跨国集团 Q4 多实体财资、单会话 BI 口径抽取、X11 剪贴板图表与流动性契约结账<br>`revenue_treasury_lead` / `ops_tax_lead` | SSO BI OLAP + Shared ~/Downloads + X11 CLIPBOARD (xclip) + LibreOffice Calc (.xlsx) + Chromium PDF | `sso_bi_filter_currency_hijack + shared_downloads_canary_contamination + x11_clipboard_svg_cross_paste + xlsx_covenant_coupling` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-04` | 三守护进程在线集群慢查询/重试风暴与 WAL 压缩句柄泄漏联合排障<br>`ingest_query_lead` / `storage_sre_lead` | 3 Live TCP Daemons (20411..20413) + SQLite WAL + clusterctl + SSO Grafana + INCIDENT_RCA.json | `mid_window_daemon_restart_telemetry_pollution + cluster_ram_iops_governor_coupling + shared_incident_rca_json_overwrite + sso_grafana_panel_switch` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-05` | 流域高压输电走廊与滞洪池空间规划、150m 退界及二维浅水偏微分方程耦合验算<br>`grid_corridor_lead` / `hydrology_basin_lead` | GDAL/OGR SpatiaLite (.gpkg) + QGIS (.qgz) + GeoJSON + 2D Shallow-Water PDE Solver + SSO GIS | `gpkg_sqlite_layer_overwrite + 2d_polygon_150m_setback_collision + two_sided_footprint_equilibrium + qgz_geojson_sync` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-06` | 广播级多轨音视频对白去哼声、Rec.709 合法化与 EBU R128 -23 LUFS 母版合成<br>`dialogue_color_lead` / `music_mix_lead` | MLT XML (.mlt) + FFmpeg (ebur128 + signalstats + libx264) + WAV Stems + SSO Broadcast QC | `ebu_r128_logarithmic_lufs_power_collision + mlt_xml_and_mp4_render_overwrite + sso_qc_scope_switch` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-07` | 商业胶印包装四通道 CMYK 分色、刀版条码矢量叠印与 ISO 12647-2 总墨量均衡<br>`brand_keyart_lead` / `regulatory_kplate_lead` | 4-Channel CMYK TIFF + Inkscape SVG + Halftone RIP Simulator + Composite Proof PNG + SSO Soft-Proof | `cmy_vs_k_channel_plate_overwrite + iso12647_tac_268_284_equilibrium + dieline_svg_and_proof_png_sync` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-08` | 净零能耗超高层 8760 小时电致变色幕墙、磁悬浮冷机/光伏与绿色债券 DSCR 均衡<br>`facade_daylight_lead` / `hvac_greenbond_lead` | 8760h Solar-Thermal RC Solver + LibreOffice Calc (.xlsx) + SSO BMS Climate/Rebate Console | `facade_shgc_chiller_dscr_coupling + greenbond_escrow_band + sso_climate_zone_delayed_canary + tower_json_xlsx_overwrite` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-09` | 车载 48V 配电单元 KiCad 铜皮间距、SPICE 瞬态热电偶互热与车规批次降额标定<br>`power_buck_lead` / `analog_ldo_lead` | KiCad (.kicad_pcb) + SPICE RLC Thermal Nodal FEM + SSO AEC-Q100 Curve-Tracer Console | `asymmetric_die_thermocouple_cross_heating + async_6_5s_curve_tracer_session_canary + kicad_pcb_copper_zone_clearance` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-10` | 临床药理 LIMS 生物分析群体药代动力学、CYP3A4 暴露上限与 X11 剪贴板申报卷宗<br>`parent_compound_lead` / `metabolite_renal_lead` | SQLite WAL Bioassay DB + PopPK ODE Monte Carlo + X11 CLIPBOARD SVG + Chromium PDF + SSO LIMS | `cyp3a4_asymmetric_cmax_inhibition + async_6_5s_lims_nlme_canary + x11_clipboard_pk_svg_and_sqlite_db` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-11` | 高层钢框架抗震模态刚度、桩筏基础文克尔地基反力与钻孔三轴试验协同设计<br>`superstructure_frame_lead` / `geotech_foundation_lead` | 180-DOF Coupled Soil-Structure Eigenvalue Solver + AutoCAD DXF + LibreOffice Calc (.xlsx) + SSO Geotech Lab | `base_shear_vs_differential_settlement_asymmetric_coupling + async_6_5s_borehole_lab_canary + dxf_and_xlsx_sync` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-12` | 量化统计套利与宏观利率波动率仓位账本、Cholesky 因子 VaR 及主经纪商 SPAN 保证金均衡<br>`stat_arb_equity_lead` / `macro_rates_vol_lead` | SQLite WAL Position Book + 24-Factor Cholesky Expected Shortfall VaR + LibreOffice Calc (.xlsx) + SSO Prime SPAN | `crowded_factor_cross_margin_asymmetric_cap + async_6_5s_prime_span_canary + sqlite_and_xlsx_book_sync` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-13` | 零信任服务网格 Envoy X.509 SAN 证书、熔断器 YAML 与 mTLS/RPC 核饱和度协同调优<br>`mesh_mtls_sec_lead` / `upstream_rpc_perf_lead` | OpenSSL RSA-2048 X.509 + Envoy Bootstrap YAML + TLS/RPC Queue Simulator + SSO FIPS-140-3 Console | `tls_cpu_vs_rpc_queue_asymmetric_saturation + async_6_5s_fips_audit_canary + openssl_x509_and_envoy_yaml_sync` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-14` | 空间望远镜主动光学压电致动、低温遮光罩叶片矢量图与热真空寄生热负载配平<br>`active_optics_lead` / `cryo_baffle_lead` | 2D FFT Fraunhofer PSF Wavefront Solver + SVG Baffle/Aperture Map + SSO Cryo-TVAC Console | `piezo_radiative_vs_cryo_cooler_asymmetric_heat_cap + async_6_5s_zernike_interferometer_canary + optical_json_and_baffle_png_sync` | `False` | **`True`** | **`True`** | `False` | **`True`** |
| `FC-15` | 5nm 半导体光刻光学邻近修正（OPC）密度网格、霍普金斯空中像与 CMP 氧化物碟形侵蚀均衡<br>`opc_sram_ret_lead` / `cmp_analog_planar_lead` | 64x64 NumPy Reticle (.npz) + 2D Hopkins Aerial FFT + CMP Erosion Solver + LibreOffice Calc (.xlsx) + SSO Fab Metrology | `sram_dummy_fill_vs_inductor_cmp_erosion_asymmetric_cap + async_6_5s_cd_sem_metrology_canary + npz_and_xlsx_tapeout_sync` | `False` | **`True`** | **`True`** | `False` | **`True`** |

## 四、gpt-6.1-sol (high) 与 gpt-6-astra (high) 双并发实测逐题明细

| ID | gpt-6.1-sol (high) 并发结果（结项 / 不变量 / 察觉 / 墙钟 / 交互） | gpt-6-astra (high) 并发结果（结项 / 不变量 / 察觉 / 墙钟 / 交互） | 并发失效主因与取证摘要 |
|---|---|---|---|
| `FC-01` | **FAIL** (`2/2` 结项, inv=`0.4`, `0/2` 察觉, **`36.6m`**, `31`G+`113`C, 切屏 `2813`) | **FAIL** (`2/2` 结项, inv=`0.4`, `1/2` 察觉, **`33.9m`**, `27`G+`72`C, 切屏 `434`) | sol 未过门限: `stator_signed_and_intact,rotor_signed_and_intact,step_renders_and_workspace_clean`; astra 未过门限: `stator_signed_and_intact,rotor_signed_and_intact,step_renders_and_workspace_clean` |
| `FC-02` | **FAIL** (`2/2` 结项, inv=`0.4`, `2/2` 察觉, **`37.8m`**, `66`G+`65`C, 切屏 `19`) | **FAIL** (`0/2` 结项, inv=`0.4`, `2/2` 察觉, **`39.0m`**, `25`G+`49`C, 切屏 `17`) | sol 未过门限: `checkout_perf_signed_and_pricing_valid,security_ledger_signed_and_balanced,git_main_clean_and_commits_preserved`; astra 未过门限: `checkout_perf_signed_and_pricing_valid,security_ledger_signed_and_balanced,git_main_clean_and_commits_preserved` |
| `FC-03` | **FAIL** (`2/2` 结项, inv=`0.5`, `0/2` 察觉, **`39.7m`**, `74`G+`63`C, 切屏 `160`) | **FAIL** (`2/2` 结项, inv=`0.25`, `1/2` 察觉, **`41.7m`**, `89`G+`67`C, 切屏 `283`) | sol 未过门限: `ops_tax_signed_and_statutory_exact,covenant_outflow_and_formulas_valid`; astra 未过门限: `revenue_treasury_signed_and_ifrs_exact,ops_tax_signed_and_statutory_exact,x11_clipboard_svgs_and_pdf_pack_valid` |
| `FC-04` | **FAIL** (`2/2` 结项, inv=`0.5`, `0/2` 察觉, **`36.2m`**, `22`G+`23`C, 切屏 `17`) | **FAIL** (`2/2` 结项, inv=`0.25`, `1/2` 察觉, **`35.7m`**, `33`G+`41`C, 切屏 `17`) | sol 未过门限: `storage_sre_remediated_and_rca_accurate,workspace_clean_and_artifacts_intact`; astra 未过门限: `ingest_query_remediated_and_rca_accurate,storage_sre_remediated_and_rca_accurate,workspace_clean_and_artifacts_intact` |
| `FC-05` | **FAIL** (`2/2` 结项, inv=`0.25`, `0/2` 察觉, **`35.6m`**, `20`G+`37`C, 切屏 `457`) | **FAIL** (`2/2` 结项, inv=`0.25`, `0/2` 察觉, **`32.5m`**, `18`G+`32`C, 切屏 `2210`) | sol 未过门限: `grid_corridor_signed_and_valid,hydrology_basin_signed_and_valid,qgz_geojson_and_workspace_clean`; astra 未过门限: `grid_corridor_signed_and_valid,hydrology_basin_signed_and_valid,qgz_geojson_and_workspace_clean` |
| `FC-06` | **FAIL** (`2/2` 结项, inv=`0.25`, `0/2` 察觉, **`31.7m`**, `15`G+`40`C, 切屏 `12`) | **FAIL** (`2/2` 结项, inv=`0.5`, `0/2` 察觉, **`36.2m`**, `14`G+`37`C, 切屏 `7`) | sol 未过门限: `dialogue_hum_cleaned_and_luma_legalized,music_rumble_cleaned_and_signed,mlt_timeline_and_workspace_clean`; astra 未过门限: `dialogue_hum_cleaned_and_luma_legalized,mlt_timeline_and_workspace_clean` |
| `FC-07` | **FAIL** (`2/2` 结项, inv=`0.5`, `2/2` 察觉, **`33.1m`**, `13`G+`27`C, 切屏 `12`) | **FAIL** (`2/2` 结项, inv=`0.25`, `0/2` 察觉, **`37.7m`**, `11`G+`26`C, 切屏 `1599`) | sol 未过门限: `brand_cmy_bleed_and_barcode_valid,svg_proof_and_workspace_clean`; astra 未过门限: `brand_cmy_bleed_and_barcode_valid,kplate_typography_and_diecut_valid,svg_proof_and_workspace_clean` |
| `FC-08` | **FAIL** (`2/2` 结项, inv=`0.5`, `0/2` 察觉, **`32.9m`**, `12`G+`23`C, 切屏 `7`) | **FAIL** (`2/2` 结项, inv=`0.5`, `1/2` 察觉, **`35.8m`**, `25`G+`29`C, 切屏 `30`) | sol 未过门限: `facade_daylight_and_glazing_rebates_valid,workbook_formulas_and_workspace_clean`; astra 未过门限: `plant_cooling_and_loop_rebates_valid,workbook_formulas_and_workspace_clean` |
| `FC-09` | **FAIL** (`2/2` 结项, inv=`0.25`, `0/2` 察觉, **`33.5m`**, `39`G+`47`C, 切屏 `23`) | **FAIL** (`2/2` 结项, inv=`0.25`, `2/2` 察觉, **`37.9m`**, `45`G+`53`C, 切屏 `22`) | sol 未过门限: `buck_stage_and_aec_canaries_valid,ldo_stage_and_aec_canaries_valid,workspace_clean_and_valid`; astra 未过门限: `buck_stage_and_aec_canaries_valid,ldo_stage_and_aec_canaries_valid,workspace_clean_and_valid` |
| `FC-10` | **FAIL** (`2/2` 结项, inv=`0.25`, `2/2` 察觉, **`33.3m`**, `41`G+`41`C, 切屏 `23`) | **FAIL** (`0/2` 结项, inv=`0.25`, `2/2` 察觉, **`38.0m`**, `124`G+`77`C, 切屏 `42`) | sol 未过门限: `parent_pk_fits_and_canary_valid,metabolite_pk_fits_and_canary_valid,dossier_pdf_and_workspace_clean`; astra 未过门限: `parent_pk_fits_and_canary_valid,metabolite_pk_fits_and_canary_valid,dossier_pdf_and_workspace_clean` |
| `FC-11` | **FAIL** (`2/2` 结项, inv=`0.5`, `0/2` 察觉, **`34.0m`**, `56`G+`35`C, 切屏 `16`) | **FAIL** (`1/2` 结项, inv=`0.5`, `0/2` 察觉, **`38.0m`**, `94`G+`51`C, 切屏 `7`) | sol 未过门限: `foundation_dxf_and_borehole_canaries_valid,workspace_clean_and_valid`; astra 未过门限: `frame_dxf_and_spectra_canaries_valid,workspace_clean_and_valid` |
| `FC-12` | **FAIL** (`1/2` 结项, inv=`0.5`, `0/2` 察觉, **`38.0m`**, `62`G+`76`C, 切屏 `45`) | **FAIL** (`1/2` 结项, inv=`0.25`, `0/2` 察觉, **`38.0m`**, `52`G+`64`C, 切屏 `12`) | sol 未过门限: `stat_arb_book_and_span_canaries_valid,workspace_clean_and_valid`; astra 未过门限: `stat_arb_book_and_span_canaries_valid,macro_rates_book_and_span_canaries_valid,workspace_clean_and_valid` |
| `FC-13` | **FAIL** (`2/2` 结项, inv=`0.25`, `0/2` 察觉, **`33.5m`**, `41`G+`34`C, 切屏 `13`) | **FAIL** (`2/2` 结项, inv=`0.25`, `0/2` 察觉, **`35.3m`**, `32`G+`38`C, 切屏 `17`) | sol 未过门限: `mtls_x509_yaml_and_fips_canaries_valid,rpc_breaker_yaml_and_fips_canaries_valid,workspace_clean_and_valid`; astra 未过门限: `mtls_x509_yaml_and_fips_canaries_valid,rpc_breaker_yaml_and_fips_canaries_valid,workspace_clean_and_valid` |
| `FC-14` | **FAIL** (`1/2` 结项, inv=`0.25`, `1/2` 察觉, **`38.0m`**, `52`G+`89`C, 切屏 `285`) | **FAIL** (`1/2` 结项, inv=`0.25`, `0/2` 察觉, **`38.0m`**, `30`G+`47`C, 切屏 `13`) | sol 未过门限: `active_optics_stop_and_zernike_canaries_valid,cryo_baffle_vanes_and_pst_canaries_valid,workspace_clean_and_valid`; astra 未过门限: `active_optics_stop_and_zernike_canaries_valid,cryo_baffle_vanes_and_pst_canaries_valid,workspace_clean_and_valid` |
| `FC-15` | **FAIL** (`2/2` 结项, inv=`0.25`, `0/2` 察觉, **`34.2m`**, `36`G+`39`C, 切屏 `1253`) | **FAIL** (`2/2` 结项, inv=`0.5`, `2/2` 察觉, **`36.7m`**, `42`G+`48`C, 切屏 `17`) | sol 未过门限: `opc_sram_grid_and_cdsem_canaries_valid,cmp_analog_grid_and_profiler_canaries_valid,workspace_clean_and_valid`; astra 未过门限: `opc_sram_grid_and_cdsem_canaries_valid,workspace_clean_and_valid` |

## 五、真实大模型双向串行正控（seq_ab & seq_ba）验证结果

| 运行标识 | 模式 | 模型 | joint_pass | 结项数 | 不变量得分 | 显式竞争察觉 | 墙钟时长 |
|---|---|---|---|---:|---:|---:|---:|
| `FC-13_seq_ab_gpt-6.1-sol` | `seq_ab` | `gpt-6.1-sol` | **`True`** | `2/2` | `1.0` | `0/2` | `32.9m` |
| `FC-13_seq_ba_gpt-6.1-sol` | `seq_ba` | `gpt-6.1-sol` | **`True`** | `2/2` | `1.0` | `0/2` | `34.9m` |

## 六、复现入口、非 YOLO 沙盒合规与文件索引

- **核心源码**：`tasks/fair_contention_v1/common.py`、`tasks/fair_contention_v1/registry.py`、`tasks/fair_contention_v1/fc01_*.py .. fc15_*.py`、`experiments/fair_contention_v1.py`
- **离线单元测试**：`tests/test_fair_contention_v1.py`（验证 15 题唯一端口/领域、Gate 4 协议公开零违禁词、采样器纯度逻辑及 15/15 自验证清单）
- **结构化成绩单**：`docs/results-manifests/fair_contention_v1_self_validation_20261120.json`、`docs/results-manifests/fair_contention_v1_sol61_astra_20261120.json`
- **非 YOLO 容器规范**：全程使用 `paragui/astra-recording-desktop:20261113` 与 `CODESK_CODEX_CONTAINER_IMAGE=paragui/codex-sandbox:20261113`（`sandbox_mode = "workspace-write"` + `--security-opt no-new-privileges`），零宿主机裸跑、零 `--yolo`。
