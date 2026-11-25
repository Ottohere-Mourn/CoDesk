# Work Order — Fulfillment & SLA Frontend Engineer (`orders_ui_eng`)

Explore every interactive control, filter pill, popover, and header shortcut dialog inside the **Orders & SLA** module of the live **Chronos ERP** application open in Chromium (`http://127.0.0.1:19612`), and implement the Orders route module inside `/workspace/chronos_suite`:

1. Use the desktop GUI driver to click through all interactive buttons, filter pills (`ALL`, `HOLD_CUSTOMS`, `CHILLED_QA`), the `SLA Penalties` popover, and the `Shortcuts (?)` modal in the **Orders & SLA** view of Chromium.
2. Implement `/workspace/chronos_suite/modules/orders_module.js` and wire it cleanly into the shared SPA shell (`/workspace/chronos_suite/index.html` and `styles.css`, preserving `<script src="modules/capacity_module.js"></script>` and `#nav-capacity`!) so that loading `index.html` at `1440x900` renders the default **Orders & SLA** view (`#nav-orders`) and clicking `#filter-hold` filters to `HOLD_CUSTOMS` rows.
3. Write `/workspace/chronos_suite/orders_discovery.json` with:
   - `topbar_hex`, `rail_hex`, `hold_order_ids` (sorted list), `tier_a_penalty_usd_hr` (int), `shortcut_export_hotkey` (string)
