---
name: paragui-collab-case-design
description: "Design, build, or audit explicit peer-aware collaborative multi-agent shared-desktop (GUI + CLI) benchmark cases in ParaGUI/CoDesk where partners know each other exists and have genuine interdependent workflows. Use when authoring or reviewing collaborative shared-workstation tasks (`dual_desktop` vs `shared_desktop`). Use $paragui-case-design instead for blind independent co-tenant tasks that require solo `isolated` baselines."
metadata:
  short-description: "Build & audit explicit collaborative GUI+CLI benchmark cases"
---

# ParaGUI / CoDesk Explicit Collaborative Benchmark Case Design

Build and audit multi-agent shared-workstation (`GUI + CLI`) benchmark cases where **agents are explicitly told a partner is working with them to complete a joint mission**, tasks feature **genuine cross-role interdependence**, and collaboration happens over **real open-source desktop/web software**.

## How This Skill Differs from `$paragui-case-design`

| Dimension | `$paragui-case-design` (Blind Co-Tenancy) | `$paragui-collab-case-design` (Explicit Collaboration) |
|---|---|---|
| **Peer Awareness in `task.md`** | Blind—never mention another agent | **Explicit—state the partner's role, scope, and shared goal** |
| **Inter-Agent Dependency** | Forbidden—each role must be solo-runnable | **Required—neither role can finish the joint mission alone** |
| **Control vs. Contention Arms** | `isolated` (1 agent) vs. `shared` (2 agents) | **`dual_desktop`** (2 agents, separate screens + shared project) vs. **`shared_desktop`** (2 agents, **1 shared screen** + shared project) |
| **Coordination Protocol** | Implicit environmental self-healing | **Emergent collaboration** (file/repo/doc notes, handoffs, pre-exit joint verification—never scripted in prompt) |

## Core Design Contract

### 1. Explicit, Natural Collaboration Brief (Zero Puppet Coordination)
- **State the Partnership Clearly in `task.md`**: Every role's work order must state:
  1. Your own role, private inputs/tools, and domain responsibilities.
  2. Your partner's role (`<partner_role>`), that they are working concurrently with you, and which upstream/downstream metrics or subsystems they own.
  3. The shared project directory (e.g., `/workspace/shared_project`), open desktop applications, and the **joint acceptance criteria** both of you are accountable for at hand-in.
- **Never Script Coordination Mechanics**: **Do NOT** tell agents *how* to synchronize (never write `"create /tmp/lock"`, `"use flock"`, `"sleep 30s until B writes ready.json"`, or `"take turns clicking GIMP"`). Let models invent their own handoff notes, Git commits, state checks, and window etiquette.

### 2. Genuine Interdependence & Why `dual_desktop` Replaces Solo `isolated`
- **True Complementary Information Split**: Give Role A access to domain-A raw sources/apps (producing intermediate parameters or artifacts `X`) and Role B access to domain-B raw sources/apps (producing `Y`), where completing the final engineering/clinical/financial deliverable **genuinely requires both `X` and `Y`** (see [references/collab-patterns-and-traps.md](references/collab-patterns-and-traps.md) for concrete interdependence topologies). Do not put fake `0 / PENDING` solo-fallback hacks in the grader.
- **Two-Arm Scientific Comparison (`dual_desktop` vs. `shared_desktop`)**:
  1. **`dual_desktop` (Collaboration Control Arm)**: Role A and Role B each get an isolated X11 display (`:99` per container) and separate GUI app processes, while sharing `/workspace/shared_project` (and shared backend DB/Git/web state if part of the workflow). This measures pure asynchronous collaboration + domain difficulty (target **`0.45-0.85`** non-saturated score) with **zero** physical mouse, keyboard-focus, modal, or singleton-GUI collision.
  2. **`shared_desktop` (Shared-Workstation Contention Arm)**: Role A and Role B collaborate on **one shared `:99` display**, sharing active window focus, modals, XKB layout, clipboard, and singleton desktop apps (`soffice.bin`, `GIMP`, `Blender`, `FreeCAD`, `QGIS`, `Qt5 Designer/Linguist`, authenticated `Chromium`).
  3. **Primary Contention Signal**: Measurable degradation `Score_shared_desktop < Score_dual_desktop` (alongside token, latency, focus-flip, and misrouted-keystroke telemetry). Keep scoring weights and denominators **100% identical** between `dual_desktop` and `shared_desktop`—never apply an asymmetric `j_mult` multiplier.

### 3. Single-Case Authenticity & 100% Real Open-Source Software
- **Real Software Only**: Launch real production/open-source desktop and web software (`LibreOffice Calc/Writer/Impress`, `GIMP 2.10`, `Inkscape 1.2`, `Blender 3.4` 3D/VSE, `FreeCAD 0.20`, `QGIS 3.22 + SpatiaLite`, `Qt5 Designer/Linguist/Assistant`, `Chromium`, `SQLite`, `Git`, `FFmpeg/SoX`). **Ban** ~80-150 line inline `PyQt`/`GTK`/`Tk` toy mockups.
- **Authentic War-Room Co-Tenancy**: Pair two roles that genuinely sit at or remote into the same war-room/lab/edit-bay workstation (e.g., hardware thermal + embedded firmware on a lab bench; clinical PK + safety pharmacovigilance on a regulatory terminal; documentary VSE editor + sound mixer in a post bay; M&A QoE + tax counsel in a closing room).
- **Goal-Driven Prompts & Blind Offline `grade()`**: Never leak formulas, submenu paths, or JSON scrape checklists in `task.md`. Keep oracle checks strictly in read-only post-episode `grade()`, parse native files with real toolchains (`PyQt5.uic.loadUi`, headless `LibreOffice`, `FreeCAD`, `QGIS`, `Blender`) rather than fragile XML tag regexes, and enforce **strict `pass_threshold = 1.0`** (`pass_a`, `pass_b`, and `joint_pass` require 100% of subchecks passed with zero errors; never mask failed checkpoints behind `0.78-0.92` thresholds, and never test undocumented/unrendered oracle easter-eggs or private-JSON vs. shared-file catch-22s).

### 4. Standardized Evaluation Runtime Protocol (Mandatory)
- **Zero Step / Tool-Call Limits (严禁步数上限)**: Set `max_cua_calls = None`. **Never** cap GUI or CLI tool calls in metadata or MCP bridges, and **never** mention a step/call ceiling in the wrapper prompt.
- **Anti-Deadlock Wall-Clock Timeout `>= 7200s` (`2h+`) Only**: Set `dual_role_timeout_s >= 7200` and `conc_role_timeout_s >= 7200` strictly as an outer infinite-loop circuit breaker. **Do not** inject countdown `time budget: ...s` text into the agent prompt.
- **Fixed Reasoning Effort = `high`**: Standardize `model_reasoning_effort = "high"` (`--effort high`) across all evaluated models unless explicitly running an effort ablation.
- **Clean GUI-Driver Isolation & Non-YOLO Sandbox**: Enforce `Xvfb :99 -auth /tmp/x99.auth` (never `-ac` across shared container networks), run `guest_bash` under a separate UID (e.g., `UID 2000`) when sharing `--pid` so `/proc/<pid>/root` cannot bypass GUI apps, never mount raw `:99` X11/AT-SPI sockets into `guest_bash`, never inject post-exit `Ctrl+S` in `stop_and_grade()`, and enforce Non-YOLO permissions (`no-new-privileges`, zero API key leaks).

## Mandatory 5-Gate Deterministic Well-Posedness Check (Zero LLM Calls)

Every collaborative case must pass all five deterministic reference checks before live model runs:

1. **`Gate 1 — pristine_fail`**: Untouched initial state fails (`joint_pass == False`, score `<= 0.20`).
2. **`Gate 2 — gt_solo_insufficient`**: Running **only Role A's solver** (`solo_a`) yields `joint_pass == False`, AND running **only Role B's solver** (`solo_b`) yields `joint_pass == False`—proving genuine mutual interdependence rather than disguised solo tasks.
3. **`Gate 3 — gt_dual_desktop_collab_passes`**: Cooperative two-agent reference solver on `dual_desktop` achieves `1.0` (`joint_pass == True`) under both `A-first` and `B-first` start staggers (zero hidden ordering deadlock).
4. **`Gate 4 — gt_naive_shared_desktop_corrupts`**: Naive uncoordinated `shared_desktop` execution (clobbering shared GUI state, modal/focus conflict, or premature exit before verifying partner handoff) fails (`joint_pass == False`, measurable score drop).
5. **`Gate 5 — gt_coordinated_shared_desktop_passes`**: Careful concurrent cooperative solver on `shared_desktop` achieves `1.0` (`joint_pass == True`) in real seconds (`<< 7200s`, zero multi-minute busy-wait loops).

## Static & Harness Audit Command

Run the dedicated collaborative auditor on every task module and runner before spending LLM evaluation tokens:

```bash
python3 ~/.codex/skills/paragui-collab-case-design/scripts/audit_collab_case.py <path/to/task_dir_or_runner.py>
```

Fix every `FAIL` and review every `WARN` before running model evaluations.
