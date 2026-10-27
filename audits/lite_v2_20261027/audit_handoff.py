"""Audit the v2 saved-revision/message/GUI chronology without trusting citations."""
from __future__ import annotations
import json
from pathlib import Path
import sys


def lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def audit(root: Path) -> dict:
    bridge = lines(root / "workspace_versions/events.jsonl")
    messages = lines(root / "collaboration/events.jsonl")
    b_stdout = lines(root / "actor_runs/B/B/stdout.log")
    oracle_path = root / "oracle.json"
    oracle = json.loads(oracle_path.read_text()) if oracle_path.exists() else {}
    a_revs = [x for x in bridge if x.get("event") == "revision_saved"
              and x.get("actor") == "A" and x.get("revision", 0) > 0]
    a_rev = a_revs[-1] if a_revs else None
    handoff_msgs = [x for x in messages if x.get("actor") == "A" and x.get("recipient") in ("B", "all")
                    and a_rev and x.get("timestamp", 0) > a_rev.get("time", 0)]
    message = None
    read_index = None
    for candidate in handoff_msgs:
        for i, item in enumerate(b_stdout):
            payload = item.get("item") or {}
            if (item.get("type") == "item.completed" and payload.get("server") == "collaboration"
                    and payload.get("tool") == "read_messages"
                    and candidate["message_id"] in json.dumps(payload.get("result", {}))):
                message, read_index = candidate, i
                break
        if message is not None:
            break
    if message is None and handoff_msgs:
        message = handoff_msgs[0]
    b_edit_indices = [i for i, item in enumerate(b_stdout) if
                      item.get("type") == "item.started" and
                      (item.get("item") or {}).get("server") == "desktop" and
                      (item.get("item") or {}).get("tool") in {"click", "type_text", "key", "drag"}]
    # Actor B may inspect or prepare the draft before A's message. Require
    # at least one later GUI edit plus a saved B revision after the message.
    post_read_edit = next((i for i in b_edit_indices if read_index is not None and i > read_index), None)
    b_revs = [x for x in bridge if x.get("event") == "revision_saved"
              and x.get("actor") == "B" and x.get("revision", 0) > 0]
    b_rev = b_revs[-1] if b_revs else None
    transfers = [x for x in bridge if x.get("event") == "transfer_verified"
                 and x.get("actor") == "A" and a_rev
                 and x.get("revision") == a_rev.get("revision")]
    source_delivered = bool(a_rev and (a_rev.get("delivered") or transfers))
    artifact_success = bool(oracle.get("joint_success"))
    strict = bool(a_rev and message and read_index is not None and post_read_edit is not None
                  and b_rev and b_rev.get("time", 0) > message.get("timestamp", 0)
                  and source_delivered and artifact_success)
    return {
        "run_id": root.name, "artifact_joint_success": artifact_success,
        "a_revision": {k: a_rev.get(k) for k in ("revision", "sha256", "time") } if a_rev else None,
        "a_message": {k: message.get(k) for k in ("message_id", "timestamp") } if message else None,
        "b_read_message_stdout_item_index": read_index,
        "b_first_gui_edit_after_read_item_index": post_read_edit,
        "b_revision": {k: b_rev.get(k) for k in ("revision", "sha256", "time") } if b_rev else None,
        "a_transfer_count": len(transfers), "source_delivered": source_delivered,
        "strict_behavioral_handoff": strict,
        "caveat": "B read timing is ordered within its model event stream; the collaboration server does not timestamp reads."
    }


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve()
    result = audit(root)
    (root / "handoff_audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
