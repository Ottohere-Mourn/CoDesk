# Operational notes and pitfalls

Things that cost real debugging time when running composite OSWorld tasks at scale. Most are already handled
in code; the notes say where, so they are not undone by accident.

## Correctness of composite runs

- **One task cache per run.** `DesktopEnv` keeps per-task state under `cache_dir/<task_id>/`; OSWorld 2.0 web
  tasks store their per-run tenant cookie there. Two concurrent runs of the same task sharing a cache dir read
  each other's tenant and score a spurious 0.0. `runner.py` defaults the cache to `<out>/cache`; never point
  several runs at one cache dir.
- **Decoupled evaluation** (`combo.evaluate_tasks`). Evaluating task A with its full postconfig and then task B
  let A's Chrome `pkill` + relaunch steal focus from B's "activate Calc + Ctrl+S", silently dropping B's edit.
  All non-restarting postconfig steps run first, restarting ones after, then the metrics.
- **Identical setup steps run once** (`combo.dedupe_setup`): two Chrome tasks would otherwise both launch Chrome on
  the same debugging port. OSWorld 2.0 Chrome tasks launch Chrome + a socat forward on fixed ports inside their own
  `setup()`, which cannot be deduplicated — two of them in one Guest collide; pair a Chrome task with a non-Chrome
  one, or expect one shared Chrome.
- **Evaluators only check their own target**: one agent can "succeed" while it corrupted the other's work. Look
  at joint outcomes and the interference metric in `analyze`, not only per-task success. Checked on real runs:
  the Calc multiply task checks only cell E3 and the Calc sum task only Sheet2 (OSWorld-V2 dropped the classic
  `preserve_cells` check of Sheet1), so text typed into those workbooks by the other agent (URLs, shell
  commands) still passes; whole-file checks (Calc dedup, VS Code replace) catch it.
- **"Done" without effect**: an agent can run its edit in the other agent's window (e.g. Ctrl+H in Calc instead
  of VS Code) and report success; the file is untouched and the evaluator correctly scores 0.
- **Postconfig isolation**: each task's save steps run in their own setup call (with retries); in one call, a
  failing step or a not-ready Guest skipped the other task's save as well.
- **Order effects**: OSWorld 2.0 tasks evaluate inside their own `evaluate()`, so their postconfig cannot be
  split; run both task orders (`matrix` does this) and compare positions.
- **Barrier start**: in `parallel`, agents are released by one barrier after all are prepared, so neither gets a
  head start (an earlier version started them with a fixed stagger).
- **Controls**: `isolated` (same concurrency and endpoint load, separate Guests) separates "shared desktop" from
  "concurrent API load"; `shadow` (second client polling the Guest without acting) separates "another actor" from
  "Guest load".

## Model endpoints

- Computer-use endpoints may reject a follow-up that carries both `previous_response_id` and an `input_image`
  after a text-only turn (HTTP 400 "Computer tool only allows input image without previous response");
  `openai_cua.harden` drops the image, the model then asks for a screenshot.
- Some deployments cap one chained computer-use conversation at 50 images: keep `--max-steps` <= 48 with
  `openai-cua`, the same for all conditions.
- Shared deployments answer 429 with a short Retry-After. Both `openai_cua` and the transports retry 429 many
  times with short random sleeps (`OSCOMBO_RATE_LIMIT_RETRIES`) and print `RATE_LIMIT_RETRY n` to stderr so a
  monitor can count them; other transient errors back off exponentially.
- If the endpoint sits behind a local proxy or tunnel, a dead proxy shows up as `Connection error` in agent
  errors; `analyze`/`queue` treat it as infrastructure and retry.

## Running without KVM (QEMU TCG)

- The default TCG CPU model breaks llvmpipe in the Guest (gnome-shell aborts, black screen): use a named model
  (`Haswell-noTSX`, set by the patched provider). QEMU 6.2 rejects `thread=` inside `-machine`; pass `-accel`.
- The Guest server encodes screenshots with PNG `optimize=True`: ~20 s per frame under TCG. Build the
  `pngfast` image (`infra/make_pngfast_image.sh`): identical pixels, 1-4 s per frame.
- Boot takes minutes and the first screenshot request can take > 10 s: the provider patch raises the readiness
  wait to 30 min and the per-request read timeout to 60 s.
- Under load a Guest may return no screenshot for minutes (Blender is the worst): the step loop waits up to
  `OSCOMBO_SHOT_PATIENCE` s (300 for Blender combos) before failing the run as `INFRA`. Heavy apps want
  `OSCOMBO_GUEST_CPUS=12`.
- Concurrency: on a 96-core host, ~6 TCG Guests at once were stable; 8 made Guests stop answering mid-run.
  Other CPU-heavy jobs on the host cause the same symptom. `queue --lanes` caps runs, `isolated` runs count N.
- GNOME notification banners (e.g. "Low Disk Space") cover click targets; the runner turns banners off.
- An evaluation against a dead Guest hangs: when any agent fails with `INFRA`, evaluation is skipped and the run
  is marked for the retry pass.

## Docker

- Rootless docker works (set `DOCKER_HOST`). In unprivileged containers rootful `dockerd` may be unable to start
  containers at all; rootless needs a user namespace and, on kernels with
  `apparmor_restrict_unprivileged_userns=1`, `CAP_SYS_ADMIN` for the rootlesskit process. No cgroups means
  `--memory/--cpus` limits are not enforced: control concurrency yourself.
- The provider labels every Guest container `oscombo.run=<run name>` (from `OSCOMBO_RUN_LABEL`, set by `queue`);
  `python -m oscombo cleanup <name>` removes the containers of a killed run. Per-Guest qcow2 overlays go to
  `OSCOMBO_OVERLAY_DIR` and are deleted when the Guest stops normally; after kills, delete stale overlays.
- `pkill -f <pattern>` matches its own command line when run through `bash -c '...'`; use `pgrep -af "[p]attern"`.

## OSWorld 2.0 task classes

- Task definitions come from the OSWorld-V2 repo; many tasks download assets from Hugging Face and need
  `HF_TOKEN` with access to the asset repo. Without access, setup fails with 404/401 for those tasks. A local
  asset snapshot can be used via `OSWORLD_FILE_BASE_URL`.
- Web tasks need `WEBSITE_HOST_SUFFIX` pointing at the OSWorld web mock sites (see the OSWorld-V2 docs).
- Scores are partial credit in [0, 1]; `analyze` reports success at `--threshold` and mean scores.

## Reproducibility

- `result.json` records the oscombo and OSWorld commits (`+dirty` if modified) and the full agent specs.
- Keep outputs on durable storage (`queue --archive`); node-local disks of batch jobs disappear with the job.
