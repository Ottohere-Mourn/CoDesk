"""Existing order list query implementation. The combined-filter defect is intentional."""
from __future__ import annotations


def filter_orders(orders, query="", status="All"):
    query = str(query or "").strip().casefold()
    status = str(status or "All")
    # BUG: once a query is present this branch returns before status filtering.
    if query:
        return [row for row in orders if query in " ".join((
            str(row.get("order_id", "")), str(row.get("customer", "")),
            str(row.get("region", "")),
        )).casefold()]
    if status != "All":
        return [row for row in orders if row.get("status") == status]
    return list(orders)
