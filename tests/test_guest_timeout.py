from types import SimpleNamespace

from oscombo import guest as guest_module
from oscombo.guest import Guest


def test_execute_passes_bounded_timeout_to_guest_server(monkeypatch):
    seen = {}

    class Response:
        ok = True

        def json(self):
            return {"status": "success", "returncode": 0, "output": "ok"}

    def fake_post(url, *, json, timeout):
        seen.update(url=url, body=json, http_timeout=timeout)
        return Response()

    monkeypatch.setattr(guest_module.requests, "post", fake_post)
    guest = Guest(SimpleNamespace(vm_ip="127.0.0.1", server_port=5000))
    result = guest.execute(["true"], timeout=75)

    assert result["status"] == "success"
    assert seen["body"]["timeout"] == 75
    assert seen["http_timeout"] == (5, 75)


def test_execute_caps_guest_timeout(monkeypatch):
    seen = {}

    class Response:
        ok = True

        def json(self):
            return {"status": "success", "returncode": 0, "output": "ok"}

    monkeypatch.setattr(
        guest_module.requests, "post",
        lambda url, *, json, timeout: (seen.update(body=json) or Response()))
    Guest(SimpleNamespace(vm_ip="127.0.0.1", server_port=5000)).execute(["true"], timeout=500)
    assert seen["body"]["timeout"] == 120
