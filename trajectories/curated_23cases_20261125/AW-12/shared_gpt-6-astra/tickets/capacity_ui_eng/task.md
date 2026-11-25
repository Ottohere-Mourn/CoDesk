# Work Order — Capacity & Failover Planner Frontend Engineer (`capacity_ui_eng`)

Explore every interactive sub-tab, regional bar action, slide-over failover runbook drawer, and dark-surface toggle inside the **Capacity Planner** module of the live **Chronos ERP** application open in Chromium (`http://127.0.0.1:19612`), and implement the Capacity route module inside `/workspace/chronos_suite`:

1. Switch to **Capacity Planner** in the left navigation rail of Chromium and click through `Utilization Bars`, `vCPU Quotas`, `Toggle Dark Surface`, and the clickable `eu-central-fra` utilization bar that opens the slide-over failover runbook drawer.
2. Implement `/workspace/chronos_suite/modules/capacity_module.js` and wire it cleanly into the shared SPA shell (`/workspace/chronos_suite/index.html` and `styles.css`, preserving `<script src="modules/orders_module.js"></script>` and `#nav-orders`!) so that clicking `#nav-capacity` at `1440x900` renders **Capacity Planner** and clicking `#open-drawer-eu` opens the failover runbook drawer.
3. Write `/workspace/chronos_suite/capacity_discovery.json` with:
   - `peak_region_id` (string), `peak_utilization_pct` (int), `failover_runbook_id` (string), `eu_reserved_vcpu_quota` (int), `drawer_banner_hex`
