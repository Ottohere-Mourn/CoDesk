Update the last two pages of `~/workspace/architecture/system_topology.odg` in LibreOffice Draw.

Use `specs/platform_layers.txt` to replace the placeholders on Analytics Platform and Resilience Layer with the specified component labels, capacity/failover notes, and `Rev 2.6` footer. Preserve the other pages and their existing content. Save the ODG. Export pages 3-4 to `~/workspace/architecture/out/platform_layers.pdf`, then verify the saved ODG contains both requested page updates and the PDF was created.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. Host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them.
