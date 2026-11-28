Configure the reporting and archive schedules in `~/workspace/scheduler_lab/schedule_config.yaml`.

Read `tasks.csv` and `scheduler_rules.txt`. Add the `publish_margin` and `archive_close` jobs with the exact UTC windows, quotas, and dependencies. Preserve the one-slot worker setting and any existing schedule entries. Use the monitor at `http://127.0.0.1:18222/` to reload the configuration, trigger a dry run, review the job states, and save `out/close_schedule_report.json` with your jobs, dependency order, run revision, and outcomes. Correct any blocked job before finalizing.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. Host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them.
