# TASK_TAXONOMY

## V0 real case: CSV-001

- **Actors:** scripted GUI actor and scripted CLI actor.
- **Shared resource:** `/workspace/shared.csv`, mounted from one host-managed temporary directory into one Docker container.
- **GUI surface:** Tk window in Xvfb; scripted GUI input uses `xdotool` keyboard/window operations.
- **CLI surface:** Python command launched inside the same container with `docker exec`.
- **Independent goals:** GUI adds `G1,gui,GUI_VALUE`; CLI adds `C1,cli,CLI_VALUE`.
- **Joint goal:** exactly both rows remain in the CSV after both actors complete.
- **Interaction:** normal mode appends to the latest file state; deterministic stale-write control captures the GUI's startup state, lets CLI append, then makes GUI save the stale snapshot and overwrite the CLI row.
- **Reset:** targeted container replacement plus fresh shared directory and application restart.

## Simulated focus case: FOCUS-001

`swcub.tasks.focus` models GUI+human replay focus competition and has deterministic scripted checks. It does not yet manipulate a real X11 desktop, so it is excluded from real-environment validation claims.

## Expansion axes

Future families may vary actor pair, shared resource, conflict semantics, observation freshness, required coordination and recovery policy. Admit a task only after independent solvability, a joint solution, deterministic replay, exact final-state grading, reset verification and a naive failure control are demonstrated. Do not use random popups/delays as the only source of difficulty.
