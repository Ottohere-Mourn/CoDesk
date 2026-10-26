"""Build the human-readable report from recorded evidence, without running Guests."""
import json
from pathlib import Path
H=Path(__file__).resolve().parent
R=H.parents[1]/'runs'
s=json.loads((H/'smoke_summary.json').read_text())['runs'];final=s[-2:]
reasons=[
 '桌面API已响应但画面仍黑；脚本点错sheet并改动受保护Sales。无效基础设施尝试。',
 '应用标题已出现但文档仍空白；脚本提前输入，随后Impress未就绪。无效基础设施尝试。',
 'A通过；B的R1未完成。截图显示快速连续替换使查找框字符串混杂；R2/R3及文件保护通过，关闭重开和reset完成。属于脚本输入失败。',
 '第一个Guest截图编码超过客户端固定10秒超时；第二Guest及角色脚本未执行。',
 'Calc名称框回车后仍持有输入焦点，TSV进入名称框；按本run PID中止并保留轨迹。',
 '因上一条已定位的公共脚本缺陷随同中止；不声称此run已实测同一GUI失败。',
 '修复后完整脚本正控；不是模型实验。',
 '修复后完整双Guest脚本正控；不是模型实验。',
]
lines=['CoDesk Data-to-Deck 真实Guest脚本验收报告','证据更新：2026-10-26。数据源：smoke_summary.json及各run原始文件。',
'本报告是预设脚本正控。没有调用任务模型，两个角色脚本按阶段串行执行；不构成真实并发Shared vs Isolated模型对照。',
'本轮保留全部8次诊断/脚本尝试，不以其中通过次数计算模型成功率。用户要求模型/API配置留空，正式模型结果均为N/A。','',
'一、最终两种拓扑验收']
for x in final:
 lines += [f"{x['run_id']}: {x['status']}；A/B={x['oracle_roles']}；joint={x['oracle_joint']}；protected={x['oracle_protection']}；GUI重开证据{x['gui_reopen_evidence'].__len__()}条；reset {x['reset_guests']} Guest。"]
lines += ['两种拓扑的回收文件均由独立新进程重新调用未修改的原Oracle，结果与runner一致，见oracle_independent_recheck.json。',
'PASS仅指此脚本正控与环境生命周期验收。Oracle未检查的revision/hash显式引用、呈现质量等完整任务语义不能据此保证；也不能证明模型在原预算内可解。','',
'二、全部尝试及归因']
for x,reason in zip(s,reasons):lines += [f"{x['run_id']} | {x['status']} | A/B={x['oracle_roles']} | {reason}"]
lines += ['', '这些失败发生在预设串行脚本，没有双Agent同时输入，不能解释为共享桌面协作干扰。修复分别对应黑帧/应用绘制就绪、截图超时、Impress输入节奏及Calc名称框焦点。每次使用不同run_id，未覆写历史轨迹或产物。','',
'三、最终Smoke成本（秒，非模型效率对照）',
'run | setup至首次GUI输入 | 脚本阶段合计 | 总时长含reset | 采样QEMU CPU秒下界 | 单QEMU峰值RSS GiB | PNG文件数']
for x in final:
 peak=max((v['rss_peak_bytes'] for v in x['qemu_processes'].values()),default=0)/2**30
 lines += [f"{x['run_id']} | {x['setup_to_first_gui_action_s']} | {x['scripted_actor_elapsed_sum_s']} | {x['elapsed_including_reset_s']} | {x['cpu_seconds_sampled_lower_bound']} | {peak:.2f} | {x['png_count']}"]
lines += ['每Guest8vCPU/8GiB；Shared配置总8vCPU/8GiB，Isolated配置总16vCPU/16GiB。CPU秒含启动、操作、重开和reset，仅为采样区间下界；RSS是单个QEMU进程峰值，不是两个Guest总峰值。rootless Docker CPU cgroup为0，未使用其计数。',
'总时长截至结果写入，最后容器close另有日志。setup计至A首次GUI输入；B应用启动发生在中途，不能将该列当成完整模型实验的setup阶段。脚本阶段合计包含截图、等待和各阶段执行。',
'两种脚本所需Alt+Tab等动作不同，且本次Smoke可能同时运行，不能用耗时差推断桌面隔离收益。',
'原scripted harness未单独累计所有截图编码/传输耗时，不编造该指标。模型调用耗时、token和实际active overlap均N/A。真实桌面MCP只读probe约5.40秒，包含进程启动、协议初始化、枚举和一次截图，不等于纯截图耗时。','',
'四、双Guest工作区与通信实测']
i=final[1];ev=[json.loads(l) for l in (R/i['run_id']/'workspace_versions/events.jsonl').read_text().splitlines()]
trans=[e for e in ev if e.get('event')=='transfer_verified']
lines += [f"Isolated保存revision {i['revisions']}条，完成传输回读验证{i['verified_transfers']}次，记录同步错误{i['sync_errors']}次。"]
for e in trans:lines += [f"{e['actor']} revision {e['revision']} -> Guest {e['destination_guest']}: {e['elapsed_s']:.3f}s，SHA256={e['sha256']}"]
lines += ['上述耗时从一次publish开始计，包含源读取、验证和传输回读；不包括最长约2秒轮询等待，GUI实际写盘时刻未独立计量，不能当作完整save-to-readable延迟。',
'事件中的delivered字段在transfer_verified写入时仍是更新前值；transfer_verified事件在peer回读hash相等后产生，最终current.json的delivered=true。判定以事件类型、回读校验和最终metadata为准。',
'两个Guest均保有自己的桌面、鼠标键盘焦点与应用状态；A的ODS在B的Calc以read-only打开，B的ODP在A的Impress以read-only打开，并与原作者最终文件hash一致。reopen_evidence.json及observations.jsonl记录实际窗口标题和截图。',
'每个最终Smoke均有3条双向消息、2个附件，客户端收发/附件内容检查通过。这里使用真实loopback协议客户端；不等于模型已通过协作MCP调用这些工具。',
'跨Guest保存与读取、版本留存属于实测；越权发布、peer意外写入、坏ZIP、传输失败重试负控来自离线HTTP/controller替身测试，不能混称全部在真实Guest执行。',
'ownership约束固定发布路径和source Guest，不证明共享桌面里的真实操作者身份；模型误写与桥错误仍需未来真实轨迹归因。','',
'五、最终文件和证据入口']
for x in final:
 p=R/x['run_id'];lines += [str(p)]
 for path,info in x['artifacts'].items():lines += [f"  {path} ({info['bytes']} bytes) SHA256={info['sha256']}"]
 lines += ['  oracle.json / oracle_independent_recheck.json：评分与独立复评。',
 '  screenshots/、actor_runs/、gui_events.jsonl、observations.jsonl：原始截图与动作。',
 '  collaboration/events.jsonl、attachments/：消息与附件。',
 '  workspace_versions/：不可变revision、ownership、传输记录及current.json。',
 '  reopen_evidence.json、guest_save_evidence.json、artifact_manifest.json：保存/重开/回收hash。',
 '  source_identity.json、provenance.json、ownership.json、resource_actions.jsonl：版本与精确资源生命周期。',
 '  qemu_process_resources.jsonl、guest_resources.jsonl：资源采样。']
lines += ['Isolated的mcp_readonly_probe/另保存真实STDIO桌面MCP截图、工具日志、1280×720图像和验证结果。',
'每步都有真实截图；PNG文件数包括setup/reopen和step前后截图，不等于GUI调用数。','',
'六、结论边界与后续',
'已得到原版Data-to-Deck在Shared/Isolated拓扑的真实GUI与Oracle正控证据；正式双模型Pilot与完整对照按用户要求未运行。',
'下一步先明确模型配置与12,000 model_tokens口径，验证模型图像/工具链和并发，再执行一次小预算Pilot及一次完整预算对照。记录普通GUI错误与协作干扰各自证据，不只看最终成败。',
'清理只针对本run完整容器ID、run标签和overlay路径。最终清理核查另存cleanup-verification.json；镜像、runtime、Python环境及专用rootless daemon保留复用。']
(H/'guest_smoke_report.txt').write_text('\n'.join(lines)+'\n')
