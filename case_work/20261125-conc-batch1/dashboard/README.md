# CONC Batch 1 trajectory dashboard

Open `index.html` directly in a browser. `dashboard-data.js`, `data/`, and `assets/` must remain next to it.

If your browser restricts local files, run this from `case_work/20261125-conc-batch1/dashboard/`:

```powershell
python -m http.server 8765
```

Then open `http://127.0.0.1:8765/`. The dashboard is static; it makes no network/API requests.

`data/` holds sanitized action JSONL, visible agent messages, relay metadata, and result summaries. `assets/` holds the screenshots referenced by the action records. Raw stdout streams and relay request payloads are intentionally not included.
