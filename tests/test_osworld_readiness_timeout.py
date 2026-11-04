import io
from types import SimpleNamespace

from PIL import Image

import swcub.osworld_readiness as readiness


def _visible_png():
    image = Image.new("RGB", (64, 64))
    image.putdata([(x * 4, y * 4, (x + y) * 2) for y in range(64) for x in range(64)])
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_readiness_uses_extended_screenshot_read_timeout(monkeypatch):
    captured = {}
    body = _visible_png()

    class Response:
        status_code = 200
        content = body

        def raise_for_status(self):
            return None

    def fake_get(url, *, timeout):
        captured.update(url=url, timeout=timeout)
        return Response()

    class Log:
        def record(self, *args, **kwargs):
            pass

    episode = SimpleNamespace(
        environment_health={}, observation=None, log=Log(),
        snapshot=lambda: {"guest_container_id": "unit-test"})
    desktop = SimpleNamespace(
        vm_ip="127.0.0.1", server_port=5000, require_a11y_tree=False,
        instruction="test")
    monkeypatch.setattr(readiness.requests, "get", fake_get)

    result = readiness.wait_for_guest_desktop(episode, desktop, timeout=1, retry_interval=0)

    assert result == body
    assert captured["timeout"] == (5, 30)
    assert episode.environment_health["readiness_attempts"] == 1
    assert episode.observation["screenshot"] == body
