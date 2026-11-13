from __future__ import annotations

import json

import pytest


def test_screenshot_coordinate_mapping_and_bounds():
    from oscombo.desktop_tools import _coordinate_audit

    assert _coordinate_audit("click", {"x": 1279, "y": 719}, [1.5, 1.5], [1920, 1080])["status"] == "accepted"
    audit = _coordinate_audit("click", {"x": 127, "y": 966}, [1.5, 1.5], [1920, 1080])
    assert audit["status"] == "rejected"
    assert audit["raw_model_coordinates"] == {"x": 127, "y": 966}
    assert audit["mapped_guest_coordinates"] == [190, 1449]
    assert audit["reason"] == "y_outside_model_screenshot_[0,720)"


def test_drag_validates_both_endpoints_and_requires_observation():
    from oscombo.desktop_tools import _coordinate_audit

    audit = _coordinate_audit("drag", {"x1": 10, "y1": 20, "x2": 30, "y2": 800},
                              [1.5, 1.5], [1920, 1080])
    assert audit["status"] == "rejected"
    assert audit["reason"] == "y2_outside_model_screenshot_[0,720)"
    assert audit["mapped_guest_coordinates"] == {"start": [15, 30], "end": [45, 1200]}
    assert _coordinate_audit("move", {"x": 1, "y": 1}, [1.5, 1.5], None)["reason"] == "no_observation_yet"
    assert _coordinate_audit("click", {"x": [195, 314]}, [1.5, 1.5], [1920, 1080])["reason"] == \
        "coordinate_missing_or_non_numeric"


def test_out_of_bounds_action_is_rejected_without_guest_action_and_returns_fresh_image(
        tmp_path, monkeypatch):
    import oscombo.desktop_tools as dt

    log = tmp_path / "actions.jsonl"
    monkeypatch.setattr(dt, "LOG", str(log))
    monkeypatch.setattr(dt, "BUDGET", 10)
    monkeypatch.setattr(dt, "SETTLE", 0)
    monkeypatch.setattr(dt, "_active_window", lambda: "Calc")
    monkeypatch.setattr(dt, "_py", lambda _code: (_ for _ in ()).throw(AssertionError("must not execute")))
    png = b"fresh-observation"
    shots = iter([(png, [1.5, 1.5], [1920, 1080]), (png, [1.5, 1.5], [1920, 1080])])
    monkeypatch.setattr(dt, "_shot", lambda: next(shots))

    assert dt.run_tool("screenshot", {}) == ("OK.", png)
    message, image = dt.run_tool("click", {"x": 127, "y": 966})
    assert image == png
    assert "REJECTED" in message and "No coordinate was clamped or corrected" in message
    records = [json.loads(line) for line in log.read_text().splitlines()]
    reject = records[1]
    assert reject["executed"] is False and reject["code"] is None
    assert reject["coordinate_audit"]["raw_model_coordinates"] == {"x": 127, "y": 966}
    assert reject["coordinate_audit"]["mapped_guest_coordinates"] == [190, 1449]
    assert reject["returned_observation"]["guest_screenshot_size"] == [1920, 1080]
    assert (tmp_path / "shots" / "002.png").read_bytes() == png


def test_in_bounds_action_records_unmodified_raw_and_mapped_coordinates(tmp_path, monkeypatch):
    import oscombo.desktop_tools as dt

    log = tmp_path / "actions.jsonl"
    monkeypatch.setattr(dt, "LOG", str(log))
    monkeypatch.setattr(dt, "BUDGET", 10)
    monkeypatch.setattr(dt, "SETTLE", 0)
    monkeypatch.setattr(dt, "_active_window", lambda: "Impress")
    executed = []
    monkeypatch.setattr(dt, "_py", executed.append)
    monkeypatch.setattr(dt, "_shot", lambda: (b"frame", [1.5, 1.5], [1920, 1080]))
    dt.run_tool("screenshot", {})
    dt.run_tool("click", {"x": 100, "y": 416})
    assert executed == ["pyautogui.click(150, 624, clicks=1, interval=0.08, button='left')"]
    record = [json.loads(line) for line in log.read_text().splitlines()][1]
    assert record["coordinate_audit"]["status"] == "accepted"
    assert record["coordinate_audit"]["raw_model_coordinates"] == {"x": 100, "y": 416}
    assert record["coordinate_audit"]["mapped_guest_coordinates"] == [150, 624]


def test_tool_result_cooldown_throttles_model_turns_and_is_observable(monkeypatch):
    import oscombo.desktop_tools as dt

    now = [100.0]
    sleeps = []
    monkeypatch.setattr(dt, "TOOL_RESULT_COOLDOWN", 60.0)
    monkeypatch.setattr(dt, "_last_tool_result_at", None)
    monkeypatch.setattr(dt.time, "monotonic", lambda: now[0])

    def fake_sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(dt.time, "sleep", fake_sleep)
    assert dt._wait_before_tool_result() == 60.0
    now[0] += 10
    assert dt._wait_before_tool_result() == 50.0
    now[0] += 65
    assert dt._wait_before_tool_result() == 0.0
    assert sleeps == [60.0, 50.0]


def test_http_gray_frame_with_cursor_is_rejected_even_when_nonblack(monkeypatch):
    import io
    from types import SimpleNamespace
    from PIL import Image, ImageDraw
    import oscombo.desktop_tools as dt

    image = Image.new("RGB", (1920, 1080), (32, 32, 32))
    ImageDraw.Draw(image).polygon([(1730, 975), (1730, 990), (1740, 985)], fill="white")
    payload = io.BytesIO()
    image.save(payload, format="PNG")
    response = SimpleNamespace(status_code=200, content=payload.getvalue(), raise_for_status=lambda: None)
    monkeypatch.setattr(dt.requests, "get", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(dt, "SETTLE", 0)
    monkeypatch.setenv("OSCOMBO_SCREENSHOT_REQUIRE_NONFLAT", "1")
    monkeypatch.setenv("OSCOMBO_SCREENSHOT_MIN_NON_BLACK_FRACTION", "0.01")
    dt._request_metrics.records = []
    dt._request_metrics.call_no = 0
    with pytest.raises(RuntimeError, match="black or flat"):
        dt._shot()
    record = dt._request_metrics.records[-1]
    assert record["non_black_pixel_fraction"] == 1.0
    assert record["frame_content"]["content_ready"] is False
