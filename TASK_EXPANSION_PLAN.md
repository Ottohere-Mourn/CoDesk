# Shared-Workspace Task Expansion Plan

## Planning boundary

This document proposes task families and scenarios only. It does not register new task IDs, alter V2.0.0 task definitions/evaluators, generate episodes, or start model runs. Each family has two candidate scenarios so that later work can select 2–3 high-quality tasks per category only after testing mechanism distinctness. The first pilot should implement at most one candidate per new mechanism.

Current measured anchors are `SWCUB-FOCUS-ROUTING-001` (focus/input routing) and `SWCUB-STALE-MERGE-001` (GUI+CLI stale whole-record overwrite). New candidates must add a distinct causal failure, not merely a new app, actor pairing, model, or string value.

## Candidate task families

### 1. Control ownership and input routing — existing anchor; add variants only if distinct

**Candidate A: Focus handoff during a long edit**

- **Scenario:** GUI Actor starts a multi-field Writer edit; Human Replay switches to its own Chat/notes window and enters a separate note before GUI resumes.
- **Actor roles:** GUI Agent + Human Replay, each with an independent target file/value.
- **Shared resource:** One X11 desktop, active window, keyboard and pointer.
- **Expected failure:** GUI text or confirmation key is routed to the Human window, causing a missing GUI goal and cross-window contamination.
- **Recovery condition:** GUI agent/scheduler reactivates the target window and verifies it before resuming.

**Candidate B: Shortcut routing with a modal dialog**

- **Scenario:** GUI Actor opens a Save As dialog for its document; another actor brings a different app/modal to the foreground before the GUI shortcut sequence.
- **Actor roles:** GUI Agent + scripted GUI/Human Replay.
- **Shared resource:** Keyboard shortcut stream and desktop modal/focus stack.
- **Expected failure:** Save/close/format shortcut affects the wrong app or dialog.
- **Recovery condition:** Re-observe the active dialog, restore the intended window, and verify save target before issuing the shortcut.

**Distinctness gate:** Candidate B is worthwhile only if modal shortcut semantics produce failures not reducible to the existing text-to-wrong-window case.

### 2. Observation invalidation and stale knowledge — partly covered; isolate evidence freshness

**Candidate A: Same-window row reorder after observation**

- **Scenario:** GUI Agent observes a table row; CLI or second GUI actor sorts/inserts a row without changing application focus; the first actor resumes.
- **Actor roles:** GUI Agent + CLI or GUI Agent.
- **Shared resource:** One table/document revision and its visible row mapping.
- **Expected failure:** Agent applies a correct value to the wrong row using stale coordinates or row identity.
- **Recovery condition:** Refresh/re-read and re-ground by stable row key before editing.

**Candidate B: Browser cache invalidation without a forced focus change**

- **Scenario:** GUI Agent reads a record; CLI changes a field; the UI keeps the same tab/window and cached value until an explicit refresh.
- **Actor roles:** GUI Agent + CLI Actor.
- **Shared resource:** One browser view, cached record and backend revision.
- **Expected failure:** Agent makes a decision using a stale observation even if its later save does not overwrite the other field.
- **Recovery condition:** Detect a changed public freshness indicator or refresh and re-observe before acting.

**Distinctness gate:** Keep T2 focused on choosing/acting from stale evidence; if the main outcome is a lost write, classify that as T3 instead.

### 3. Shared-state consistency and conflicting updates — existing anchor; add a new consistency primitive

**Candidate A: Same-field conflict with a declared precedence rule**

- **Scenario:** GUI and CLI actors independently update the same status field with different valid values; task semantics specify a deterministic merge/priority rule.
- **Actor roles:** GUI Agent + CLI Actor.
- **Shared resource:** One authoritative record and revision history.
- **Expected failure:** Last-writer-wins violates the declared priority or one actor's accepted update disappears.
- **Recovery condition:** Re-read revision, apply the merge rule, and verify the resolved final value.

**Candidate B: Append-only shared activity log**

- **Scenario:** Two actors add independent entries to the same log/file through GUI and CLI interfaces.
- **Actor roles:** GUI Agent + CLI Actor.
- **Shared resource:** One append-only document/file and record ordering.
- **Expected failure:** Truncating write, duplicate retry, or missing entry violates completeness/order requirements.
- **Recovery condition:** Verify existing entries and append only the missing unique entry.

**Distinctness gate:** These candidates test same-field resolution or append semantics, unlike V2's whole-record stale overwrite.

### 4. Ephemeral shared-resource ownership — new

**Candidate A: Clipboard overwrite between copy and paste**

- **Scenario:** GUI Agent copies a required cell range for its own document; Human Replay or a second GUI Actor copies its independent note before the agent pastes.
- **Actor roles:** GUI Agent + Human Replay/GUI Agent.
- **Shared resource:** Session-wide clipboard.
- **Expected failure:** Agent pastes the other actor's content into its target, or overwrites the human's destination.
- **Recovery condition:** Re-copy/revalidate the intended payload immediately before paste, then verify both destinations.

**Candidate B: Selection/drag payload replaced mid-operation**

- **Scenario:** One actor selects rows/cells for transfer; another actor changes the shared selection or starts a separate drag/copy action.
- **Actor roles:** GUI Agent + GUI Agent or Human Replay.
- **Shared resource:** Current selection/drag payload and pointer gesture state.
- **Expected failure:** Wrong rows move, or a destination is populated with a different actor's selection.
- **Recovery condition:** Re-select by stable labels and verify the source and destination before committing.

### 5. Application and object-context ownership — new

**Candidate A: Two documents in one focused application**

- **Scenario:** Two actors use Writer with different documents; one changes the active document while the other resumes with a valid edit.
- **Actor roles:** GUI Agent + GUI Agent/Human Replay.
- **Shared resource:** Application's active-document context and shared desktop.
- **Expected failure:** Correct text is saved to the wrong document or a valid change overwrites another file.
- **Recovery condition:** Verify document identity/title and destination path before editing/saving.

**Candidate B: Browser tab or record context switch**

- **Scenario:** GUI Agent prepares an update on one local review record; CLI/Human Replay changes the active tab/record; the GUI agent resumes in the same browser window.
- **Actor roles:** GUI Agent + CLI Actor or Human Replay.
- **Shared resource:** Browser session, tab, active record and one local backend.
- **Expected failure:** Correct-looking field edit affects the wrong record/account.
- **Recovery condition:** Reconfirm stable record identity, refresh, and score only the intended record plus untouched records.

### 6. Interruption, preemption, and safe resumption — new

**Candidate A: Human changes a field during a multi-step agent transaction**

- **Scenario:** Human Replay makes an independent valid edit after the agent reads a form but before the agent's save step.
- **Actor roles:** GUI Agent + Human Replay, each with a distinct field goal.
- **Shared resource:** One form record and the agent's partial edit/checkpoint.
- **Expected failure:** Agent resumes its old plan and reverts or duplicates the human's edit.
- **Recovery condition:** Agent observes after interruption, updates only its own field, and verifies both goals.

**Candidate B: Resume after an explicit user priority interruption**

- **Scenario:** Human Replay requests a short urgent edit while an agent is midway through a longer document task, then asks it to resume.
- **Actor roles:** GUI Agent + Human Replay.
- **Shared resource:** One desktop and one or more shared documents with declared checkpoints.
- **Expected failure:** Agent loses place, repeats a destructive operation, or fails to finish one independent goal.
- **Recovery condition:** Resume from a verifiable checkpoint and re-check already completed steps before continuing.

### 7. Temporal synchronization and durability — new

**Candidate A: Read before autosave durability**

- **Scenario:** GUI Actor edits a document with delayed autosave; CLI Actor reads or appends a dependent field at a deterministic save boundary.
- **Actor roles:** GUI Agent + CLI Actor.
- **Shared resource:** One document and its asynchronous save/flush state.
- **Expected failure:** CLI acts on an old durable version or creates a duplicate after a retry.
- **Recovery condition:** Wait for a public save-complete signal, re-read durable state, then apply an idempotent update.

**Candidate B: Competing background export to a shared path**

- **Scenario:** Two actors export separate, independently required reports to one declared destination/name policy while the first export is still finalizing.
- **Actor roles:** GUI Agent + CLI Actor or second GUI Agent.
- **Shared resource:** Export queue and shared destination path.
- **Expected failure:** Partial file, wrong final file, or reordering that silently drops one report.
- **Recovery condition:** Use a declared unique naming/commit protocol and verify file hashes after writes settle.

## Selection and implementation gates

1. Keep the two V2 anchors as calibration controls; do not rewrite them to fit a new category.
2. For the next implementation slice, prioritize **clipboard ownership** and **application/object context** because their expected failures are distinct from currently measured focus routing and stale-save overwrite.
3. Add at most one scripted pilot per new category initially. The second candidate is retained only if it exercises a different interaction primitive and adds an evaluator predicate not already covered.
4. Before promotion, each candidate must pass: actor-by-actor Solo controls, joint feasibility, deterministic trigger, evaluator negative signature, declared recovery, clean reset, ownership provenance, and a real-Guest run.
5. Keep the current model/evaluator fixed during comparisons. Do not add random timing noise; use deterministic event barriers and record action/observation revisions.
6. Do not launch a model matrix or batch-generate instances until the scripted pilot and its evaluator are reviewed.

## Proposed next-stage order

1. Write a one-page spec for clipboard ownership and check it against T1/T2 overlap.
2. Implement scripted solo/shared/recovery episodes for one clipboard pilot in a new task version/instance.
3. If the evaluator demonstrates a distinct, reproducible failure, add a second clipboard task candidate; otherwise revise or drop the family.
4. Repeat the same gated process for application/object context, then interruption and temporal synchronization.
5. Expand same-field conflict and append-only consistency only after confirming that they add new consistency primitives beyond V2.
