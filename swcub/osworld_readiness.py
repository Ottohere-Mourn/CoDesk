"""Bounded visual and accessibility readiness checks for OSWorld V2.1 Guests."""
from __future__ import annotations

import io
import time
from typing import Any

import requests
from PIL import Image


def wait_for_guest_desktop(episode: Any, desktop: Any, timeout: float = 300,
                           retry_interval: float = 3) -> bytes:
    """Wait until the screenshot is visible and required accessibility is available.

    Guest readiness is an infrastructure predicate, separate from task evaluation.
    It records ordinary blank-screen boot polling separately from accessibility
    service failures, and never starts actors with missing required focus state.
    """
    started = time.monotonic()
    deadline = started + timeout
    last_reason = "screenshot endpoint not ready"
    attempts = 0
    health = episode.environment_health
    require_tree = bool(getattr(desktop, "require_a11y_tree", False))
    while time.monotonic() < deadline:
        attempts += 1
        accessibility_tree = None
        visible = False
        screenshot_size: list[int] | None = None
        visible_ratio = 0.0
        try:
            response = requests.get(
                f"http://{desktop.vm_ip}:{desktop.server_port}/screenshot",
                timeout=(5, 10))
            response.raise_for_status()
            image_bytes = response.content
            with Image.open(io.BytesIO(image_bytes)) as image:
                screenshot_size = list(image.size)
                pixels = list(image.convert("RGB").resize((64, 64)).getdata())
            visible_ratio = sum(max(pixel) > 24 for pixel in pixels) / len(pixels)
            visible = visible_ratio > 0.05 and len(set(pixels)) > 16
            if not visible:
                last_reason = f"blank screenshot, visible_ratio={visible_ratio:.4f}"
            elif require_tree:
                tree_response = requests.get(
                    f"http://{desktop.vm_ip}:{desktop.server_port}/accessibility",
                    timeout=(5, 10))
                if tree_response.status_code == 200:
                    payload = tree_response.json()
                    candidate = payload.get("AT") if isinstance(payload, dict) else None
                    if isinstance(candidate, str) and candidate.strip():
                        accessibility_tree = candidate
                        health["readiness_accessibility_successes"] = (
                            health.get("readiness_accessibility_successes", 0) + 1)
                    else:
                        last_reason = "accessibility endpoint returned no usable tree"
                else:
                    last_reason = f"accessibility endpoint HTTP {tree_response.status_code}"
                if accessibility_tree is None:
                    health["readiness_accessibility_failures"] = (
                        health.get("readiness_accessibility_failures", 0) + 1)
        except (requests.RequestException, OSError, ValueError) as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            if visible and require_tree:
                health["readiness_accessibility_failures"] = (
                    health.get("readiness_accessibility_failures", 0) + 1)

        if visible and (not require_tree or accessibility_tree is not None):
            episode.observation = {"screenshot": image_bytes,
                                   "accessibility_tree": accessibility_tree,
                                   "instruction": getattr(desktop, "instruction", None)}
            elapsed = round(time.monotonic() - started, 3)
            health["readiness_attempts"] = health.get("readiness_attempts", 0) + attempts
            episode.log.record(
                "environment", "healthcheck", "guest.desktop_ready",
                {"ready": False}, {"ready": True}, outcome="ready",
                details={"guest_container_id": episode.snapshot().get("guest_container_id"),
                         "attempts": attempts, "elapsed_seconds": elapsed,
                         "visible_ratio": visible_ratio,
                         "accessibility_tree_available": accessibility_tree is not None,
                         "accessibility_tree_chars": len(accessibility_tree or ""),
                         "screenshot_size": screenshot_size})
            return image_bytes

        episode.log.record(
            "environment", "healthcheck", "guest.readiness_retry",
            {"ready": False}, {"ready": False}, outcome="retry",
            details={"guest_container_id": episode.snapshot().get("guest_container_id"),
                     "attempt": attempts, "reason": last_reason,
                     "screenshot_visible": visible})
        health["readiness_retry_count"] = health.get("readiness_retry_count", 0) + 1
        time.sleep(retry_interval)
    raise TimeoutError(f"OSWorld Guest did not become ready: {last_reason}")
