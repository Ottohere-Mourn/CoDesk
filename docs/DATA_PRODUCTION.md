# Data production plan

This is the CoDesk data-production plan; references to V0 describe the historical Shared-Workspace prototype and remain unchanged for provenance.

1. **Scenario authoring:** V0's [`tasks/v0_manifest.json`](../tasks/v0_manifest.json) is the first versioned task catalog. New tasks should describe app initial state, actor roles/instructions, action graph, intended race, independent solutions, joint solution, evaluator predicates and deterministic schedule in that manifest schema or a deliberately versioned successor.
2. **Scripted verification:** implement baseline and recovery actors; replay from reset at least twice; assert byte-stable final state and equivalent event sequence. Use negative-state fixtures to ensure the grader rejects lost updates and misdirected text.
3. **Human replay capture:** capture consented, task-focused action traces (window/action/timing/state transitions) with secrets removed; parameterize timing windows but pin replay schedule per release. Include multiple valid human traces where real variation matters.
4. **Task review:** independent reviewers check clarity, solvability, realism, interaction necessity, licensing, shortcut resistance, and evaluator validity. Remove tasks solvable by a single actor if claimed interaction capability is not tested.
5. **Difficulty ladder:** no contention; controlled interaction; recovery required; repeated/long-horizon interaction. Keep deterministic trigger conditions and avoid random-noise-only items.
6. **Release:** task manifest, environment image/app versions, resets, actor instructions, action schemas, evaluator code/version, scripted baselines, event schema, provenance, and checksums. Keep test/evaluator details isolated where leakage matters.
7. **Model evaluation:** freeze model/runtime settings, run paired seeds/schedules and actor-role swaps, retain raw traces and failure categories, report compute/latency. Consider GPU use only after a suitable local model/harness is selected; current simulator is CPU-only and does not benefit from GPU.

Initial expansion targets: repeated focus races across dialogs/browser tabs; CSV/SQLite or spreadsheet stale writes with explicit version semantics; clipboard ownership; browser state changes across actors; duplicate/ordered actions in a shared mock backend. Each family needs varied app/task content, not just renamed instances.
