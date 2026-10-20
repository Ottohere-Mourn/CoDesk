# oscombo — composite OSWorld tasks on one shared desktop

Run several **official OSWorld tasks in one Ubuntu Guest at the same time**, each driven by its own agent that
only sees its own instruction, and score every task with **its own official evaluator**. The question this
answers: what happens to GUI agents when they share one desktop (focus theft, keystrokes landing in the other
agent's window, one task's setup/evaluation disturbing the other), compared with running the same tasks alone.

Models and agent harnesses are pluggable: anything that implements OSWorld's `predict(instruction, obs)` agent
interface plugs into the built-in step loop, and whole external agent programs (the codex and pi CLIs, or any
other program) drive the Guest through the same set of desktop tools.

## Run modes

| mode | Guests | what runs |
|---|---|---|
| `solo` | 1 | one task alone (baseline) |
| `sequential` | 1 | all task setups in one Guest; agent A runs to completion, then B, ... |
| `parallel` | 1 | all task setups in one Guest; all agents start together (one barrier) and act concurrently |
| `isolated` | N | control: agents run concurrently through the same code path, each task in its own Guest |
| `shadow` | 1 | control: all setups in one Guest; agent A acts, the others only poll the Guest like an agent would |

Tasks: `<domain>/<uuid>` (classic OSWorld examples), `v2/<NNN>` (OSWorld 2.0 task classes), or a task file path.
Combos can hold more than two tasks; agents are named `agentA`, `agentB`, ... in task order.

How tasks share one Guest (`oscombo/combo.py`): the first task goes through the official `DesktopEnv.reset`,
the others run their setup steps through the same setup controller, and identical setup steps run once.
Evaluation is decoupled: every task's non-restarting postconfig steps (activate window, save) run first, then
the restarting ones (deduplicated), then each task's metric — evaluating tasks one after another with full
postconfig lets one task's app restart steal focus from the other's save and silently drop its edits.

## Layout

```
oscombo/
  osworld.py        locate the OSWorld checkout (OSWORLD_DIR), load task specs, normalize scores
  guest.py          the shared Guest: screenshots with patience, focused-window probe, pyautogui execution
  combo.py          boot, multi-task setup, decoupled multi-task evaluation
  runner.py         run modes, agent threads, result.json / trace.jsonl
  harness/          HOW an agent drives the Guest
    base.py           Harness interface (prepare / run -> AgentResult)
    step_loop.py      "step": screenshot -> policy.predict -> execute pyautogui (official OSWorld loop)
    external.py       "command": any program; "codex": codex CLI + MCP tools; "pi": pi agent + same tools
    pi_desktop.ts     pi extension exposing the desktop tools
  policies/         WHICH model decides the next action inside the step loop
    base.py           Policy interface (= OSWorld mm_agents interface), action normalization
    openai_cua.py     "openai-cua": official GPTResponseAPIAgent (native computer tool), hardened transport
    osworld_agents.py "chat-pyautogui" / "responses-pyautogui" / "osworld-agent" (any mm_agents class)
    transports.py     OpenAI-compatible /chat/completions and /responses transports (replace call_llm)
    scripted.py       "scripted": fixed actions, no model (smoke tests)
  desktop_tools.py  desktop tools over the Guest HTTP API: MCP server (codex) or one call per process (pi)
  mediation.py      optional harness-level fixes for shared desktops: input broker, window ownership, self-guard
  analyze.py        success by condition/position, partial credit, joint outcomes, cross-window interference
  cli.py            python -m oscombo {run, matrix, queue, analyze, cleanup}
infra/
  setup_osworld.sh  clone OSWorld-V2 (pinned osworld-v2.1), download + verify the Guest image, venv, patch
  patch_osworld.py  docker provider patch: runtime image / overlay dir / Guest size / timeouts / labels via env
  qemu-runtime/     QEMU container image with a TCG fallback for hosts without /dev/kvm
  build_runtime.sh  build it
  make_pngfast_image.sh  derive a Guest image with fast (non-optimized) PNG screenshots, for TCG hosts
configs/env.example.sh   every environment variable in one place (copy to env.sh, git-ignored)
lists/              combo definitions (OSWorld 1 and 2.0) and a smoke list
docs/NOTES.md       operational notes and pitfalls found while running this at scale
tests/              unit tests with an in-memory DesktopEnv (no Guest needed)
```

## Setup

Requirements on the machine that runs the Guests: Linux x86-64, docker (rootless works), `git`, `uv`, `curl`,
`unzip`, ~20 GB disk for the image plus a few GB per concurrent Guest. `/dev/kvm` is strongly recommended;
without it see "No KVM" below.

```bash
export OSWORLD_DIR=/path/to/OSWorld-V2 OSWORLD_IMAGE_DIR=/path/to/images
bash infra/setup_osworld.sh            # --with-mcp: external (MCP) harnesses; --with-v2-tasks: OSWorld 2.0
                                       # task classes (gated, needs HF_TOKEN)
cp configs/env.example.sh env.sh       # fill in paths and the model endpoint, then:
source env.sh
python -m pytest -q                    # unit tests (no Guest)
```

**No KVM** (e.g. inside a container): build the TCG runtime and a fast-screenshot Guest image once.

```bash
bash infra/build_runtime.sh                                   # -> oscombo/qemu-runtime:local
export OSCOMBO_RUNTIME_IMAGE=oscombo/qemu-runtime:local
bash infra/make_pngfast_image.sh "$OSWORLD_IMAGE_DIR/osworld-v2-ubuntu-x86.qcow2" \
                                 "$OSWORLD_IMAGE_DIR/osworld-v2-ubuntu-x86.pngfast.qcow2"
export OSCOMBO_GUEST_IMAGE=$OSWORLD_IMAGE_DIR/osworld-v2-ubuntu-x86.pngfast.qcow2
```

## Running

```bash
# pipeline smoke test, no model: two tasks in one Guest, scripted agents that just say DONE
python -m oscombo run --mode parallel --policy scripted --out runs/smoke \
    --tasks chrome/bb5e4c0d-f964-439c-97b6-bdb9747de3f4 libreoffice_calc/42e0a640-4f19-4b28-973d-729602b5a4a7

# one real run: OpenAI computer-use model (endpoint from OPENAI_BASE_URL / OPENAI_API_KEY)
python -m oscombo run --mode parallel --policy openai-cua --model <model> --max-steps 48 --out runs/p1 \
    --tasks chrome/bb5e4c0d-f964-439c-97b6-bdb9747de3f4 libreoffice_calc/42e0a640-4f19-4b28-973d-729602b5a4a7

# an experiment: expand combos (both task orders x modes x repeats + solo baselines), run 4 at a time
python -m oscombo matrix lists/osworld1_combos.txt --prefix e1 --mode parallel:2 --mode sequential:1 > runs_e1.txt
nohup python -m oscombo queue runs_e1.txt --out-root runs --lanes 4 --run-timeout 7200 --archive /durable/dir \
    -- --policy openai-cua --model <model> --max-steps 48 > queue.out 2>&1 &
python -m oscombo analyze runs --prefix e1-
```

`queue` skips runs that already have a `result.json`, gives every run its own task cache, retries runs that
failed for infrastructure reasons once (the failed attempt is kept under `runs/_infra/`), and logs one line per
run to `runs/queue_<list>.log`. A killed run's Guest containers can be removed with
`python -m oscombo cleanup <run name>`.

Output per run (`runs/<name>/`): `result.json` (mode, tasks, task ids, scores, per-agent status/steps/errors,
timings, agent specs, code versions), `trace.jsonl` (one record per agent step with the focused window before
each action), `start.png`, `end.png`, per-step screenshots, and `driver.log` when run through `queue`.

## Models (policies, for the `step` harness)

| `--policy` | model side | notes |
|---|---|---|
| `openai-cua` | Responses API with the native `computer` tool | official `GPTResponseAPIAgent`; endpoint from `OPENAI_BASE_URL` (Azure `.../openai/v1` works) |
| `chat-pyautogui` | any OpenAI-compatible `/chat/completions` VLM (vLLM, SGLang, ...) | official `PromptAgent`, screenshot in, pyautogui code out; `--base-url` |
| `responses-pyautogui` | `/responses`-only models without the computer tool | official `O3Agent` planner |
| `osworld-agent` | any `mm_agents` class | `--opt agent_class=mm_agents.uitars_agent:UITARSAgent --opt agent_kwargs='{...}'`, optional `--opt transport=chat` |
| `scripted` | none | `--opt actions='["pyautogui.click(10, 10)"]'` or `--opt file=actions.json` |
| `pkg.module:factory` | yours | `factory(env, spec)` returns an object with `reset()` and `predict(instruction, obs)` |

A policy is the OSWorld agent interface: `predict(instruction, {"screenshot": png_bytes, ...})` returns
`(raw_response, actions)` where actions are pyautogui code strings or `DONE` / `FAIL` / `WAIT` (strings or
OSWorld action dicts). Set `needs_a11y = True` on the policy to also receive `accessibility_tree`.

## Harnesses

| `--harness` | what drives the Guest |
|---|---|
| `step` (default) | the step loop around a policy (above) |
| `codex` | unmodified codex CLI with only the desktop tools over MCP (no shell, read-only sandbox); `--model`, `--effort`, `--opt base_url=...`, `--opt node_bin=...` |
| `pi` | unmodified pi agent with only the desktop tools as an extension (no built-in tools); same options |
| `command` | any program: `--opt command='["my-agent", "--url", "{guest_url}", "--task", "{instruction_file}"]'` |
| `pkg.module:Class` | a `oscombo.harness.Harness` subclass: `prepare(ctx)`, `run(ctx) -> AgentResult` |

External programs get `OSCOMBO_GUEST_URL`, `OSCOMBO_INSTRUCTION`, `OSCOMBO_INSTRUCTION_FILE`,
`OSCOMBO_AGENT_DIR`, `OSCOMBO_ACTION_LOG`, `OSCOMBO_MAX_STEPS`, `OSCOMBO_MODEL`, `OSCOMBO_PASSWORD`. They can
use `python -m oscombo.desktop_tools --mcp` (stdio MCP) or `python -m oscombo.desktop_tools <tool> '<json>'`
(screenshot, click, drag, move, type_text, key, scroll, wait, declare_infeasible): every call returns a 1280x720
screenshot, counts against the budget (`--max-steps`, screenshots included) and is written to the action log the
run trace is built from. Exit code 0 = done, budget used up = max_steps, `<agent_dir>/INFEASIBLE` = the agent
declared the task infeasible.

Note: these desktop tools are ordinary function tools; `openai-cua` uses the model's native `computer` tool on
the full 1920x1080 screen, so step-harness and external-harness results are not directly comparable.

Different agents in one run can use different models and harnesses:

```bash
python -m oscombo run --mode parallel --out runs/mixed --tasks chrome/<id> libreoffice_calc/<id> \
    --agents '[{"policy": "openai-cua", "model": "model-a"}, {"harness": "codex", "model": "model-b"}]'
```

## Harness-level mitigations and prompt ablations

`--mediation` (parallel mode, `step` harness) adds what a product runtime could do about input/focus contention:
`broker1` (one agent at a time observes / acts, each on its own window), `broker2` (+ keyboard input into another
agent's window is refused and the agent told), `selfguard` (each agent refocuses only its own windows). Window
ownership comes from the windows each task's setup opened (`setup_windows` in result.json). `--coagent-hint`
appends "this computer may be shared ..." to every instruction. Both are recorded as `variant` and reported as
separate conditions by `analyze` (e.g. `parallel[broker2]-1`).

## Tests

`python -m pytest -q` runs the pipeline (all modes, setup dedup, decoupled evaluation, infra handling,
harnesses, transports, analysis) against an in-memory DesktopEnv.
