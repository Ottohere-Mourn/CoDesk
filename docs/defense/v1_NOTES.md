# Defense v1: design notes (blue team)

Code: `v1.py` (`--defense v1`). It runs per harness only and keeps no shared state. It never mentions other
actors, and the same code path runs for every task and mode.

## 1. Baseline on this round's pool (18 pairs, dataset v1)

| mode | both pass |
|---|---|
| solo | 72/72 single tasks pass |
| seq | 36/36 |
| par (no protection) | **6/72 (8%)** |
| sg (SelfGuard) | **2/72 (3%)** |

There are 156 failing agents in par+sg. All of them end with `[INFEASIBLE]`, after a median of 15 steps (par) or
19 steps (sg), typically 5–10 minutes. 122 of the 156 explicitly reason about "another agent", "concurrent
input", "external control" or "tool malfunction" (keyword scan of the reasoning summaries).

## 2. Failure taxonomy (root cause per failing agent)

I read 51 par/sg runs closely: W 12, X 12, M+F 14, D+O 13 (including the two worked examples). For each failing agent
I took the first interference event that set it on the path to giving up.

| class | W | X | M/F | D/O | total | per-harness fix? |
|---|---|---|---|---|---|---|
| **A** one browser window/tab/login form/cookie session for both (login typed twice, tab navigated away, typing into the same address bar) | 10 | 4 | – | (1) | **14** | yes, M5 |
| **B** keys/clicks land in another window: focus moved between screenshot and action; typing at 33 chars/s gets split; "Ctrl+Alt+T + type the script" in one batch types the script into the document that was in front | (in A) | 4 | 3 | 4 | **11** | yes, M2/M3 |
| **G** two agents type into one gnome-terminal (B adopts A's terminal, or both scripts interleave char by char) | 2 primary, contributes in 12/16 | – | 9 | 6 contributing | **11** | yes, M3+M6 |
| **F** inside one single-window app: one Thunderbird main window (folder tree, selection); one VS Code window with one integrated terminal (Ctrl+\` toggles the other agent's panel) | – | 6 | 1 (VLC) | 7 | **14** | VS Code terminal: guidance only; Thunderbird: no |
| **I** SelfGuard bound to the wrong "own" window (setup-window ownership is wrong when both tasks reuse the same app windows; it re-raised Chrome, a black Thunderbird or the desktop-icons window before every action, so terminal commands landed in Chrome/Thunderbird/GNOME search) | 5 | 1 | 5 | 3 | **14** (sg only) | yes: v1 does not use setup ownership |
| **D** lost update: a stale copy written back over the other agent's work (`o3`: A restores its backup; `o2-par-redlinesFirst-r2`: B rebuilt the docx from a `/tmp` snapshot) | – | – | (3 doc corruptions, secondary) | 2 | **2** | guidance only |
| **H** final step: `[INFEASIBLE]` on suspicion while the state was still recoverable (the partner usually finished) | 16/16 | ~12/16 | 17/17 | ~all | – | guidance (M1) |
| env (exclude or rerun) | `w3-par-callsFirst-r1` (Chrome crash, app refused) | `x3-sg-cateringFirst-r2` (root fs read-only), `x1-par-reportFirst-r2` (refused + low disk, likely) | – | – | 3 runs | – |

The rows overlap: a run usually shows A or B first, then G, then H. Example runs:

- **A:** `v1-w1-sg-pgw1triageFirst-r1`, `v1-w2-par-pgw2claimFirst-r1` (neither agent ever gets logged in), `v1-x3-par-pgx3rsvpFirst-r2`
- **B:** `v1-f2-par-pgf2fileFirst-r2` (a heredoc typed into the workbook), `v1-x4-sg-pgx4claimsFirst-r1` (keys hit Thunderbird shortcuts and archive mail)
- **G:** `v1-m1-par-pgm1rulesFirst-r2`, `v1-x1-par-pgx1reconFirst-r2`
- **F:** `v1-d2-par-pgd2kelvarFirst-r2`, `v1-x2-par-pgx2schedFirst-r1`
- **I:** `v1-d4-sg-pgd4tableFirst-r1`, `v1-m1-sg-pgm1rulesFirst-r2`
- **D:** `v1-o3-sg-pgo3budgetFirst-r1`

What the model sees before it gives up is almost always foreign text: commands it did not type in "its" terminal,
a username typed twice, or "26 password dots". It concludes that the tools are broken or that something external
controls the computer. The system prompt says "hard blockers → [INFEASIBLE]", so it gives up.

**Environment note for the lead (rule 5, not mine to change).** Thunderbird starts as a black window in every M run,
including the seq runs. That pushes all M/X agents into terminals (reading mbox files, `pkill thunderbird`), which is
where most G collisions happen.

## 3. Mechanisms in v1 and the classes they target

| | mechanism | targets | why it is harmless alone |
|---|---|---|---|
| M1 | Generic notes appended to the instruction (identical for every task, checked against `FORBIDDEN`). (a) Windows, focus, files and pages may change on this live desktop; this is never a hard blocker; look again and continue; [INFEASIBLE] only if the task itself is impossible. (b) Don't close, revert, undo or overwrite things that are not part of your task. (c) Never write back an older copy or backup; save the current content plus your changes. (d) Use a terminal window (Ctrl+Alt+T), not a terminal panel inside another app; wait to see a new window before typing into it. | H, D, F (VS Code panel), B (Ctrl+Alt+T race) | It only rules out giving up for reasons that do not exist alone, and the practices it asks for are correct anyway. |
| M2 | **Act on what you saw.** Each action is wrapped in the same Guest process. The first action of a batch goes to the window shown in the model's screenshot (re-activated if the focus moved). Later actions go to the window the previous action left in front, but a window that appeared during my batch (my dialog) is accepted. If my previous action should open a window that has not appeared yet, the next action waits for it (≤10 s) instead of typing into whatever is in front. | B | The focus only moves through my own actions; the only cost is waiting for windows the agent itself asked for. |
| M3 | **Fast, held input.** Text is typed at full speed, one character at a time. Before each character the active window is read through python-xlib (`_NET_ACTIVE_WINDOW`, well under 1 ms; xdotool fallback). If an older window took the focus, the harness waits 1 s (so the other window's screenshot can happen) and takes the focus back. If it cannot get it back within 15 s, it drops the rest of the text rather than typing elsewhere. Keys, hotkeys and clicks get the same hold. `moveTo(); click()` is fused into `click(x, y)`, so the shared pointer cannot move in between. | B, G | Same keystrokes and clicks at the same places, only faster (the official agent types 33 chars/s, so a 2,000-char script takes about 60 s). |
| M4 | **Own view.** Before each screenshot, the window my last action left in front ("home") is re-activated if another window is in front. Windows that appeared during or right after my own action, or for my pending window-opening action, are adopted and never hidden. After the screenshot (`observe`), if the front window changed while it was being captured, home is raised again and the screenshot retaken (≤3 times). | C, B, I | Fires only if a program steals the focus, which is then undone; the agent's own new windows always stay visible. |
| M5 | **Own browser profile.** At `start()` (sequential, before any agent acts), if a Chromium-family window is open: copy the user's `Default` profile (cookies, logins, prefs; no caches, session files or locks) to `Assist-<random>` and open it in the running browser (`--profile-directory`, so same process and same debug port) with the open tabs, front tab first. Logins, logouts and per-session server state (filters, roles, calendar week) are then this harness's own. Any action that lands in a browser window I don't own brings up my own instead. Fallbacks: a new window of the shared profile, then no M5. | A | The same pages and same cookies appear in a fresh window. |
| M6 | **Own terminal.** Ctrl+Alt+T is executed as `gnome-terminal --window --role=<private random role>`, so the harness knows exactly which terminal is its own (falls back to the hotkey if that fails). Terminals are adopted only by that role. If an action lands in a terminal that appeared after start and is not mine, my own terminal is brought up (or a new one is made). | G | Ctrl+Alt+T still opens a terminal in `~`. Terminals open at start (task setup) stay usable. |
| M7 | **Close fallback.** If I close something and the focus falls on a later window that is not mine, my previous window comes back. | B | Never fires alone, because all later windows are mine. |

Ownership is never derived from the task setup, which was SelfGuard's error (class I). Windows open at start are
"the user's" windows and usable by anyone. Windows that appear later belong to whoever's action made them appear.

**Offline tests (no GUI):**

- **Unit:** guidance vs `FORBIDDEN`; code rewriting; the wrapped program compiles behind the controller's prefix line
  and runs against a stub pyautogui. Bookkeeping is written even when the action raises.
- **Fake desktop:** fake `xdotool`/`wmctrl`/`xprop`/`google-chrome`/`gnome-terminal` sharing one state file, and two
  Defense instances acting in lockstep with 0.3–1.5 s "inference". Solo: all text lands in the right window. Parallel:
  login text stays in each harness's own browser window and scripts stay in each harness's own terminal, except a few
  stray characters at the exact moment of a focus switch. The fake is much slower per key than the Guest and its
  checks use the xdotool fallback.

## 4. Expected effect

- A, B, G and I account for about 50 of the 66 analysed root causes, and M2–M6 remove their mechanics.
- M1 removes the "suspicion → [INFEASIBLE]" step for whatever interference is left.
- I expect par both-pass to rise from 8% to roughly 35–50%. Most remaining failures should be in class F (shared
  Thunderbird main window, one VS Code window, one LibreOffice document) and in data-level conflicts (same file,
  same server records), where the agents now keep going instead of giving up.
- Overhead: about 3 Guest round trips per step plus about 0.3 s per action (≤10% of a ~28 s step). This is offset by
  much faster typing.
- One-time cost: profile copy plus a browser window in `start()`, which runs before the agent clock.

## 5. Risks (please check `defense_stats` in result.json)

- **Untested on the real Guest.** Blue may not run the GUI. Each mechanism degrades to a no-op if a tool is missing,
  so watch these counters:
  - `browser_own_profile`, `browser_windows_made`: did `--profile-directory` forwarding to the running Chrome work?
  - `adopted` / `terminal_*`: did `gnome-terminal --role` work from the Guest server's environment (it needs the
    session D-Bus)?
  - `action_refocused`, `observe_restored`, `observe_retaken`: how often focus fights happen.
  - `errors`: failed Guest calls.
- **The copied browser profile** may show a welcome/intro tab or a profile name in the window title. Its exit state is
  patched to "clean" so no "Restore pages?" bubble appears. Cookies set less than about 30 s before the copy (not yet
  flushed) are missing: a task whose setup logs in through the browser just before start would need a fresh login.
  OSWorld-style checkers that read bookmarks/settings of the `Default` profile would not see changes made in the
  copy (none in this pool).
- **Sequential runs.** B's profile is copied at start, before A runs, so B logs in itself (all W/X instructions give
  credentials). B's browser window is refreshed once on its first screenshot if it is older than 90 s.
- **Focus contention.** When both agents act at once the focus alternates, and input is held rather than misdelivered.
  If the focus cannot be regained within 15 s the rest of the text is dropped; the model sees missing text and
  retypes. A window that appears during my inference and was not caused by my pending launch is hidden from my next
  screenshot by design. My own very slow window (more than 45 s) would be hidden once.
- **Terminals opened other ways** (dock, menu) are not recognised as mine and get replaced by a role terminal on the
  next step.

## 6. Not fixable per harness (in v1)

- **One single-window application used by both:**
  - Thunderbird main window: folder tree, selection, message list. The profile is locked and both tasks need the same
    mailbox.
  - VS Code: one window and one integrated terminal; M1 only steers agents to terminal windows.
  - One LibreOffice document: shared content, shared undo stack, "Save document?" dialogs. A second view
    (Window > New Window) would separate cursor and selection; candidate for v2, but it needs a Guest probe first.
- **Data-level conflicts:** the same file written by both, the same server records, the same mailbox files edited
  from a terminal while Thunderbird runs, an app restarted (`pkill thunderbird`) under the other agent. M1 only
  reduces these.
- **The `[INFEASIBLE]` decision itself.** `FAIL` is handled by the runner before any hook sees it.

## 7. Hook requests for v2 (for everyone)

1. `on_finish(kind, text) -> str | None`, called when the model outputs `[INFEASIBLE]` (or `[DONE]`). Returning a
   generic text sends it back as the next user turn instead of ending the run, at most once or twice per run. Example:
   "Before you stop, take a fresh screenshot and retry the step that failed once more; only stop if the task itself is
   impossible." Every failing agent ended this way while its state was still recoverable, so this is likely the
   single biggest lever left.
2. Pass the action dict's `batch_index`/`batch_last` to `transform_action` and `after_action`.
3. Pass the `execute_python_command` response (stdout) to `after_action`. The private scratch file would then not be
   needed.
