Update the first two pages of `~/workspace/architecture/system_topology.odg` in LibreOffice Draw.

Use `specs/core_services.txt` to replace the placeholders on Core Services and Customer Platform with the specified component labels, link/capacity notes, and `Rev 2.6` footer. Preserve the other pages and their existing content. Save the ODG. Export pages 1-2 to `~/workspace/architecture/out/core_services.pdf`, then verify the saved ODG contains both requested page updates and the PDF was created.

You may freely choose the desktop GUI, `guest_cli`, or a combination. `guest_cli` can read, create, edit, and execute files within the Guest workspace. It runs inside this OSWorld Guest, not on the HealthCare host. Host-side Oracle, ground truth, evaluation data, and queue control are not exposed to `guest_cli`; do not access or alter them.
