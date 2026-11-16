# Original OSWorld contention comparison

The user selected ten pairs of original OSWorld tasks, prioritizing shared
applications and files. The frozen selection is
[osworld_contention10.json](../lists/osworld_contention10.json): three Calc pairs,
three Chrome pairs, and four VS Code pairs. Task instructions, input definitions,
and official evaluators retain their original contents and recorded SHA-256 hashes.

Each pair runs four times in fresh desktop VMs: Codex parallel, Freehand parallel,
Codex sequential, and Freehand sequential. The sequential control sets up both
tasks together, then runs agent A followed by B. Both conditions evaluate the final
shared state after both agents finish. Harness order is counterbalanced across
pairs. A shared filename alone is insufficient evidence of a race; sequential
success and concurrent failure identify candidates for trajectory review.

The two agents in a parallel trial share one desktop, start from oscombo's barrier,
and receive only their own task instruction. Both harnesses can use Bash, files,
scripts, and GUI inside the guest, with a 1800-second limit per agent. The model is
`gpt-6-astra`, reasoning effort `high`, through the same user-provided endpoint.
Each guest has 4 vCPUs and 8 GiB RAM, with a 10 GiB container memory limit. The queue
permits two simultaneous desktop VMs and checks available host memory and disk
before starting another trial.

Codex runs the installed official CLI 0.163.0, including its native tools and
context management. It has a separate configuration/session directory for each
agent; additional agents and web-search tools are disabled. Freehand runs the
existing mini-harness adapter and runtime, retaining its editable session and
four-image request window. These native context-management differences are part
of the harness comparison. The `steps` field counts successful model responses,
not GUI actions. Codex's runtime installation occurs before the agent timer;
total run time also includes setup, installation, and evaluation.

API credentials stay on the VM10 host. Codex's relay preserves native Responses
SSE events; Freehand uses its existing gateway. Both record model usage and failed
requests. Model completion, evaluator scores, infrastructure errors, and timeouts
remain separate fields.

A passive observer records window focus and versions of the selected shared files
every 0.5 seconds. Small-file snapshots are limited to 2 MiB per version and 200
versions per watched file. It does not lock input, coordinate the agents, change
task files, or capture every short-lived filesystem transition. The original
bookmark-page task uses direct network access to its original public pages.

The VM10 batch directory is recorded in
`/data/yuke/paraGUI/active_comparison.json`. Its `manifest.json` holds the selected
tasks, source hashes, model, budgets, and runtime versions. `progress.json` tracks
the queue. `REPORT.md`, `summary.json`, and `scores.csv` update after each finished
trial. Individual results and complete trajectories are under `runs/`; each
trial's `observer.tar.gz` contains focus records and shared-file versions.

The batch entry point is `python -m experiments.contention_batch run --project
<batch-directory> --lanes 2`, run from its frozen CoDesk checkout with the existing
OSWorld Python environment. A transient systemd service keeps it running across
SSH disconnects. `python -m experiments.contention_batch report --project
<batch-directory>` rebuilds reports after the supervisor has stopped.

Configuration was checked against the installed CLI and the
[official Codex configuration reference](https://developers.openai.com/codex/config-reference/).
The native Codex preflight completed two real VS Code tasks with official scores
1.0/1.0, 11 successful model requests, and successful image transport. This
preflight is separate from the 40 formal trials. The final implementation passed
49 tests before the batch started.
