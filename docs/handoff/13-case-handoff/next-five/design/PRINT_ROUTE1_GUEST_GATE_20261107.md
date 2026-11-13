# PRINT-ROUTE1 Guest capability gate (2026-11-07)

## Decision

**NO-GO on the current pinned OSWorld Guest image.** The design requires at least two ordinary Guest-local print destinations whose selected/default state could be changed through normal desktop printing. The Guest has no CUPS destinations and no system default destination. Do not install CUPS-PDF, create fake queues, or change the image to make this candidate work.

This is a capability falsification, not a model result and not a universal claim about other Guest images.

## Probe

- Run: 'print-route-readonly-probe-20261107-161413-8da8c7'
- Machine: HealthCare; pinned image '/home/mjh/Projects/_deps/codesk-case2-ubuntu-ssd-20261101.qcow2'.
- Driver: existing OSWorld Guest constructor; pinned OSWorld '.venv/bin/python'.
- Scope: one Guest only; read-only 'lpstat -t', package presence ('cups', 'cups-client', 'cups-pdf') and '/etc/cups' listing.
- No GUI print dialog was opened because the prerequisite already failed; no document was printed.
- No model request, API call, GPU worker, host shell inside Guest, package install, printer setup, or queue creation.
- Base image mounted read-only; generated qcow overlay, cache, ledger and report placed beneath '/mnt/raid1/mjh/codesk-next-candidates-20261103/runs/print-route-readonly-probe-20261107-161413-8da8c7'.
- Runtime container was torn down. No stale container was observed afterward.

## Observed Guest state

'lpstat' is present. CUPS 2.4.1 and 'cups-client' are installed, and the scheduler is running. 'lpstat -t' repeatedly reports 'No destinations added' and ends with 'no system default destination'. 'cups-pdf' is absent. '/etc/cups' contains configuration directories but no configured print destination.

Therefore the task's two-queue/shared-default exposure is absent. Treating Chromium's possible built-in 'Save as PDF' target as a printer queue would change the mechanism into a file-save-path task and overlap the existing CWD/file-routing family. Do not silently substitute it.

## Resource and artifact audit

- Read-only preflight passed: no active Docker container, local runtime image present, root free space above the runner's 25 GiB minimum, RAID1 above 100 GiB, and 'MemAvailable' above 40 GiB.
- Post-run report records '/' free bytes '30127325184' and RAID1 free bytes '1324771725312'.
- The probe used QEMU on host CPU/KVM; it did not use GPU or call a model. Peak QEMU CPU was roughly two cores during boot.
- The successful report and resource ledger are on RAID1 at the run path above. Overlay size was approximately 78 MiB.
- An earlier setup attempt using the Actor MCP venv failed before Guest/container creation because it lacked 'gymnasium'; that attempt has a separate run directory and is not part of the capability evidence. The successful attempt used the pinned OSWorld venv.

## Follow-up

Retire PRINT-ROUTE1 for this image. If a different pinned Guest naturally supplies at least two destinations, the gate can be repeated before any task construction. Do not install or create printers to manufacture the condition. ATTACH-EVIDENCE1 remains lower-priority and should be described as a workflow-level reuse of selection/context unless a native chooser-state control establishes a distinct mechanism.
