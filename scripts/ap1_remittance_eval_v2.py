"""Host-side AP-1 v0.2 oracle. Do not install in or expose to the Guest."""
from typing import Any
from scripts import ap1_remittance_fixture_v2 as fx

ALL_DOCS = tuple(fx.SOURCE_DOCS)

def evaluate_store(data: dict[str, Any], role: str = "shared") -> dict[str, Any]:
    core = data["core"]
    a0 = fx.evaluate_a(core)
    checks = dict(a0["checks"])
    checks["all_source_documents_reviewed"] = (
        sorted(data["reviewed_source_ids"]) == sorted(ALL_DOCS))
    checks["draft_saved_by_preparer"] = data["draft_actor"] == "preparer"
    a = {**a0, "checks": checks,
         "success": a0["success"] and all(checks.values())}
    b = fx.evaluate_b(core)
    if role == "preparer":
        return {"role": role, **a}
    if role in ("credit", "credit-clerk"):
        return {"role": "credit-clerk", **b}
    if role != "shared":
        raise ValueError("role must be preparer, credit, or shared")
    return {"role": role, "success": a["success"] and b["success"],
            "actor_a": a, "actor_b": b, "events": list(data["events"])}
