"""Private clipboard sampling and evidence-based attribution for CoDesk.

The observer is evaluator-side. Its snapshots are written to the episode log and
are never returned through ActorContext or model prompts.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Protocol


class ClipboardSampler(Protocol):
    def sample(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ClipboardSnapshot:
    owner_xid: str | None
    payload_sha256: str | None
    payload_bytes: int | None
    targets: tuple[str, ...]
    generation: int | None
    active_window_xid: str | None
    active_window_title: str | None
    focused_xid: str | None
    focused_title: str | None
    status: str = "ok"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClipboardSnapshot":
        if data.get("status", "ok") != "ok":
            raise ValueError(f"clipboard observer unavailable: {data.get('error', data)}")
        digest = data.get("payload_sha256")
        if digest is not None and (not isinstance(digest, str)
                                   or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("payload_sha256 must be null or lowercase SHA-256")
        targets = data.get("targets", [])
        if not isinstance(targets, list) or any(not isinstance(x, str) for x in targets):
            raise ValueError("targets must be a string array")
        generation = data.get("generation")
        if generation is not None and (type(generation) is not int or generation < 0):
            raise ValueError("generation must be a non-negative integer or null")
        return cls(
            owner_xid=_optional_string(data.get("owner_xid")),
            payload_sha256=digest,
            payload_bytes=(data.get("payload_bytes") if type(data.get("payload_bytes")) is int
                           else None),
            targets=tuple(targets), generation=generation,
            active_window_xid=_optional_string(data.get("active_window_xid")),
            active_window_title=_optional_string(data.get("active_window_title")),
            focused_xid=_optional_string(data.get("focused_xid")),
            focused_title=_optional_string(data.get("focused_title")))

    def as_dict(self) -> dict[str, Any]:
        return {"owner_xid": self.owner_xid,
                "payload_sha256": self.payload_sha256,
                "payload_bytes": self.payload_bytes,
                "targets": list(self.targets), "generation": self.generation,
                "active_window_xid": self.active_window_xid,
                "active_window_title": self.active_window_title,
                "focused_xid": self.focused_xid,
                "focused_title": self.focused_title,
                "status": self.status}


class GuestCommandClipboardSampler:
    """Call the bundled Guest probe through the existing same-Guest CLI channel."""

    def __init__(self, execute_argv: Callable[[list[str]], str],
                 probe_path: str = "/tmp/codesk_clipboard_probe.py",
                 state_path: str = "/tmp/codesk_clipboard_observer_state.json"):
        self._execute_argv = execute_argv
        self.probe_path = probe_path
        self.state_path = state_path

    def sample(self) -> dict[str, Any]:
        raw = self._execute_argv(["python3", self.probe_path,
                                  "--state-path", self.state_path])
        try:
            result = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError("Guest clipboard probe returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise RuntimeError("Guest clipboard probe result must be an object")
        ClipboardSnapshot.from_dict(result)
        return result


def install_guest_probe(execute_argv: Callable[[list[str]], str],
                        host_probe: Path, run_id: str) -> tuple[str, str]:
    """Install this repository's probe under unique Guest /tmp paths.

    The Guest is expected to be disposable/resettable; paths are run-scoped to
    avoid overwriting another task's observer. This function never removes them.
    """
    if not re.fullmatch(r"[A-Za-z0-9._-]{8,80}", run_id):
        raise ValueError("run_id must be 8-80 safe ASCII characters")
    import base64
    data = base64.b64encode(host_probe.read_bytes()).decode("ascii")
    guest_script = f"/tmp/codesk-clipboard-{run_id}.py"
    guest_state = f"/tmp/codesk-clipboard-{run_id}-state.json"
    code = ("from pathlib import Path; import base64; p=Path(" + repr(guest_script) + "); "
            "p.write_bytes(base64.b64decode(" + repr(data) + ")); p.chmod(0o700)")
    execute_argv(["python3", "-c", code])
    return guest_script, guest_state


class ClipboardEventTracker:
    """Derive generation changes and cautiously attribute the triggering actor."""

    _COPY_CUT = re.compile(
        r"(?:hotkey\s*\([^)]*(?:ctrl|control)[^)]*(?:['\"]c['\"]|['\"]x['\"])[^)]*\)"
        r"|press\s*\(\s*['\"](?:ctrl\+c|ctrl\+x|control\+c|control\+x)['\"]\s*\)"
        r"|ctrl\+[cx])",
        re.IGNORECASE)

    def __init__(self) -> None:
        self._previous: ClipboardSnapshot | None = None

    def reset(self) -> None:
        self._previous = None

    def record(self, raw: dict[str, Any], *, actor_id: str | None = None,
               source_action: Any = None, phase: str,
               expected_payload_sha256: str | None = None) -> dict[str, Any]:
        current = ClipboardSnapshot.from_dict(raw)
        previous = self._previous
        digest_changed = bool(previous and previous.payload_sha256 != current.payload_sha256)
        owner_changed = bool(previous and previous.owner_xid != current.owner_xid)
        source = _action_text(source_action)
        if isinstance(source_action, dict) and source_action.get("op") == "key":
            copy_action = str(source_action.get("key", "")).lower().replace("control", "ctrl") in {
                "ctrl+c", "ctrl+x"}
        else:
            copy_action = bool(self._COPY_CUT.search(source))
        payload_changed = digest_changed
        # X server owner identity is deliberately reported separately. A logical
        # Actor is attributed only when a post-action digest transition matches
        # that Actor's independently known source payload. Owner handoff alone
        # can be caused by a clipboard manager and is insufficient evidence.
        digest_matches_actor_source = (expected_payload_sha256 is not None
                                       and current.payload_sha256 == expected_payload_sha256)
        logical_actor = (actor_id if phase == "after_action" and digest_changed
                         and copy_action and digest_matches_actor_source else None)
        self._previous = current
        return {**current.as_dict(), "phase": phase,
                "logical_actor": logical_actor,
                "logical_actor_attribution": ("copy_action_bracket"
                    if logical_actor is not None else "unknown"),
                "payload_changed": digest_changed,
                "selection_owner_changed": owner_changed,
                "copy_or_cut_action": copy_action,
                "digest_matches_actor_source": digest_matches_actor_source,
                "sample_duration_ms": raw.get("sample_duration_ms"),
                "payload_read": raw.get("payload_read"),
                "source_action": source[:500] if source else None}


def classify_paste(*, expected_payload_sha256: str | None,
                   observed_payload_sha256: str | None,
                   target_matches: bool | None,
                   final_content_matches: bool,
                   overwrite_between_copy_and_paste: bool | None = None) -> dict[str, Any]:
    """Classify independent clipboard/focus evidence and exact terminal outcome."""
    clipboard_mismatch = (expected_payload_sha256 is not None
                          and observed_payload_sha256 is not None
                          and expected_payload_sha256 != observed_payload_sha256)
    clipboard_overwrite = clipboard_mismatch and overwrite_between_copy_and_paste is True
    focus_mismatch = target_matches is False
    if clipboard_overwrite and focus_mismatch:
        mechanism = "mixed"
    elif clipboard_overwrite and target_matches is True:
        mechanism = "clipboard_overwrite_supported"
    elif focus_mismatch:
        mechanism = "focus_misroute_supported"
    elif (expected_payload_sha256 is None or observed_payload_sha256 is None
          or target_matches is None
          or (clipboard_mismatch and overwrite_between_copy_and_paste is None)):
        mechanism = "unknown"
    else:
        mechanism = "no_mechanism_evidence"
    return {"mechanism_evidence": mechanism,
            "clipboard_mismatch": clipboard_mismatch,
            "clipboard_overwrite_between_copy_and_paste": clipboard_overwrite,
            "focus_mismatch": focus_mismatch,
            "task_failure": not final_content_matches,
            "recovered_or_unaffected_final_state": final_content_matches}


def payload_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def has_intervening_clipboard_overwrite(observer_events: list[dict[str, Any]], *,
                                         recipient_actor: str,
                                         copy_seq: int, paste_seq: int,
                                         expected_payload_sha256: str) -> bool:
    """Require a distinct actor's bracketed copy to replace the expected digest."""
    if paste_seq <= copy_seq:
        return False
    for event in observer_events:
        if not copy_seq < int(event.get("seq", -1)) < paste_seq:
            continue
        details = event.get("details", {})
        if (event.get("actor") == "clipboard_observer"
                and details.get("phase") == "after_action"
                and details.get("source_actor") != recipient_actor
                and details.get("payload_changed") is True
                and details.get("logical_actor") == details.get("source_actor")
                and details.get("payload_sha256") not in
                    (None, expected_payload_sha256)):
            return True
    return False


def _action_text(action: Any) -> str:
    if isinstance(action, str):
        return action
    try:
        return json.dumps(action, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return str(action)


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None else None


def validate_sampler_non_perturbation(before: dict[str, Any],
                                     after: dict[str, Any]) -> dict[str, Any]:
    """Check a paired read-only probe against owner and payload state."""
    left, right = ClipboardSnapshot.from_dict(before), ClipboardSnapshot.from_dict(after)
    stable = (left.owner_xid == right.owner_xid
              and left.payload_sha256 == right.payload_sha256
              and left.targets == right.targets)
    return {"stable": stable,
            "owner_unchanged": left.owner_xid == right.owner_xid,
            "payload_unchanged": left.payload_sha256 == right.payload_sha256,
            "targets_unchanged": left.targets == right.targets,
            "note": "Offline comparison checks state equality only; Guest timing/non-perturbation still requires a real control."}
