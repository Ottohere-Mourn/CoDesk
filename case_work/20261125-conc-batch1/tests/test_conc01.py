from __future__ import annotations

import importlib.util
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from PIL import Image, ImageDraw


CASE = Path(__file__).parents[1] / "CONC-01"


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


service = load_file("conc01_service", CASE / "integration" / "service.py")
grade = load_file("conc01_grade", CASE / "private" / "grade.py")


def full_state():
    tabs = [f"tab_{i}" for i in range(1, 7)]
    peaks = {tab: {"peak_a": i + 1.125, "peak_b": i + 2.875} for i, tab in enumerate(tabs)}
    return {
        "a_controls": [{"name": n, "width": w, "height": 850} for w in (375, 768, 1440) for n in ("delivery", "promotion", "tax")],
        "a_checks": [{"band": b, "width": w, "height": h, "badge_code": str(i + 123456)} for i, (b, w, h) in enumerate((("mobile", 375, 812), ("tablet", 768, 1024), ("desktop", 1440, 900)))],
        "b_hovers": [{"tab": t, "peak": p, "width": 1920, "height": 1080} for t in tabs for p in ("peak_a", "peak_b")],
        "badges": {x["band"]: x["badge_code"] for x in [{"band": r["band"], "badge_code": r["badge_code"]} for r in [{"band": "mobile", "badge_code": "123456"}, {"band": "tablet", "badge_code": "123457"}, {"band": "desktop", "badge_code": "123458"}]]},
        "peaks": peaks,
    }


def full_workspace(root: Path):
    (root / "out_a").mkdir(parents=True, exist_ok=True)
    (root / "out_b").mkdir(parents=True, exist_ok=True)
    report = {
        "mobile": {"has_bug": True, "bug_element_id": "btn-express-pay", "badge_code": "123456"},
        "tablet": {"has_bug": True, "bug_element_id": "promo-banner", "badge_code": "123457"},
        "desktop": {"has_bug": False, "bug_element_id": "NONE", "badge_code": "123458"},
    }
    (root / "out_a" / "qa_viewport_report.json").write_text(json.dumps(report), encoding="utf-8")
    for name, size in (("qa_375.png", (375, 812)), ("qa_768.png", (768, 1024)), ("qa_1440.png", (1440, 900))):
        image = Image.new("RGB", size, "white")
        ImageDraw.Draw(image).rectangle((0, 0, 119, 23), fill="#00BFA5")
        image.save(root / "out_a" / name)
    state = full_state()
    (root / "out_b" / "ops_telemetry.json").write_text(json.dumps(state["peaks"]), encoding="utf-8")
    colors = ["#1E88E5", "#8E24AA", "#FB8C00", "#43A047", "#00ACC1", "#F4511E"]
    for i, color in enumerate(colors, 1):
        image = Image.new("RGB", (1920, 1080), "white")
        ImageDraw.Draw(image).rectangle((1800, 0, 1919, 23), fill=color)
        image.save(root / "out_b" / f"ops_tab_{i}.png")
    return state


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        service.STATE = Path(self.temp.name) / "state.json"
        service.STATE_LOCK = Path(self.temp.name) / "state.lock"
        self.servers = []
        self.threads = []
        for role in ("A", "B"):
            handler = type(f"TestHandler{role}", (service.Handler,), {"role": role})
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            self.servers.append(server)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)
        self.a_url = f"http://127.0.0.1:{self.servers[0].server_port}"
        self.b_url = f"http://127.0.0.1:{self.servers[1].server_port}"

    def tearDown(self):
        for server in self.servers:
            server.shutdown()
            server.server_close()
        self.temp.cleanup()

    def get(self, url, cookie=None):
        request = Request(url, headers={"Cookie": cookie} if cookie else {})
        try:
            response = urlopen(request)
        except HTTPError as err:
            response = err
        with response:
            raw = response.read()
            content = json.loads(raw) if "json" in response.headers.get("Content-Type", "") else raw.decode()
            return response.status, content, response.headers.get("Set-Cookie")

    def post(self, url, payload, cookie):
        request = Request(url, data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json", "Cookie": cookie})
        with urlopen(request) as response:
            return response.status, json.loads(response.read())

    def test_authentication_and_a_records(self):
        self.assertEqual(self.get(self.a_url + "/")[0], 401)
        _, _, cookie_header = self.get(self.a_url + "/bootstrap")
        cookie = cookie_header.split(";", 1)[0]
        self.assertEqual(self.get(self.a_url + "/", cookie)[0], 200)
        self.post(self.a_url + "/api/control", {"name": "delivery", "value": "express", "width": 375, "height": 812}, cookie)
        _, result = self.post(self.a_url + "/api/record", {"band": "mobile", "width": 375, "height": 812, "bug_element_ids": ["btn-express-pay"]}, cookie)
        self.assertEqual(len(result["badge_code"]), 6)
        state = service.read_state()
        self.assertEqual(len(state["a_controls"]), 1)
        self.assertEqual(state["a_checks"][0]["band"], "mobile")

    def test_b_requires_real_wide_outer_viewport(self):
        _, _, cookie_header = self.get(self.b_url + "/bootstrap")
        cookie = cookie_header.split(";", 1)[0]
        self.assertEqual(self.get(self.b_url + "/api/hover?tab=tab_1&peak=peak_a&width=1280&height=720", cookie)[0], 409)
        _, result, _ = self.get(self.b_url + "/api/hover?tab=tab_1&peak=peak_a&width=1920&height=1080", cookie)
        self.assertIsInstance(result["value"], float)
        self.assertEqual(len(service.read_state()["b_hovers"]), 1)


class GraderTests(unittest.TestCase):
    def test_full_fixture_scores_all_28_checks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            state = full_workspace(root)
            result = grade.evaluate(root, state)
            self.assertTrue(result["joint_pass"], result["flags"])
            self.assertEqual(result["actor_a"], 1.0)
            self.assertEqual(result["actor_b"], 1.0)

    def test_pristine_workspace_fails(self):
        with tempfile.TemporaryDirectory() as d:
            result = grade.evaluate(Path(d), full_state())
            self.assertFalse(result["joint_pass"])


if __name__ == "__main__":
    unittest.main()
