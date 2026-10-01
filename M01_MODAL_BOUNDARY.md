# M-01: native modal boundary check

Status: BLOCKED as a separate family after one bounded scripted Guest diagnostic. M-01 remains an optional Focus/Window ownership variant until it shows a two-Actor effect that cannot be explained by ordinary focus and input routing.

The existing `generate_modal_instance(0)` defines independent Writer and Calc Save As goals and exact output paths. The diagnostic `scripts/probe_modal_m01_boundary.py` seeds that fixture in one real Guest, opens both LibreOffice documents, verifies document readiness, then has Writer Actor A open the native Save As chooser. It records the active X11 window, `WM_TRANSIENT_FOR`, `WM_WINDOW_ROLE`, `_NET_WM_STATE_MODAL`, accessibility tree and screenshot. Calc Actor B then attempts an ordinary GUI `Alt+Tab` switch and its own `Ctrl+Shift+S` Save As command while the Writer chooser remains open. A cancels the dialog, and the run checks reset, provenance and current-run resource lifecycle.

The probe deliberately stops before treating a blocked or redirected B input as an outcome. It asks a narrow question: does a real modal ownership state appear, and is there evidence that B is blocked even when Calc is the verified active target? A focus transition or a key going to the foreground Save dialog is still a Focus/Input Routing event. If that is all the real trace shows, M-01 should merge into Focus. Only an observable application-modal ownership effect with independent Actor goals and a private oracle would justify a separate family. If the observer or UI is unstable, mark BLOCKED. No model, MA-ID success rate, or full modal task validation is inferred from this single probe.

Artifacts are run-local. The script never handles an existing container by name, image tag or prefix; its Guest lifecycle uses the project ownership identity and append-only ledger. Historical modal feasibility probes remain unmodified.

## Bounded Guest result

Run `m01-modal-boundary-20261001-r01` completed on one real A6000 Guest with Writer and Calc both passing document readiness. A opened Writer's Save chooser; X11 recorded `GtkFileChooserDialog`, `_NET_WM_STATE_MODAL` and transient parent Writer (`0xe01388`). B's GUI `Alt+Tab` activated Calc, then B's GUI `Ctrl+Shift+S` opened a second Save chooser whose transient parent was Calc (`0xe00024`). Both Save windows remained listed at once. This directly rules out a simple claim that Writer's modal state globally prevents Calc from starting its own Save As.

Two later scripted Escape actions did not close the two Save windows in this trace, despite the active-window observer showing a Save dialog. The probe did not capture a separate keyboard-focus XID or score exact saved artifacts, so it cannot distinguish modal-stack behavior from keyboard routing or a LibreOffice dialog quirk. The anomaly is **UNKNOWN**, and it is not a dual-goal failure rate.

The run retained screenshots, accessibility trees, X11 snapshots, GUI event log, provenance and a matching ownership ledger; reset passed. Decision: **BLOCKED** as an independent Modal family after the bounded de-duplication attempt. It may be revisited only with a focused keyboard-focus/owner oracle and an independent goal outcome; until then, use dialog scenarios as Focus/Window ownership variants and do not implement M-02.
