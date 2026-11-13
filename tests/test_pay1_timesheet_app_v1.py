import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from scripts import pay1_timesheet_app_v1 as app
from scripts import pay1_timesheet_fixture_v1 as fx


class Pay1AppHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="pay1-app-test-")
        cls.root = Path(cls.tmp.name)
        cls.server = cls.root / "server.py"
        cls.state = cls.root / "state.json"
        cls.server.write_text(app.server_text(fx.SOURCE_FIXTURE_SHA256), encoding="utf-8")
        compile(cls.server.read_text(encoding="utf-8"), str(cls.server), "exec")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.proc = subprocess.Popen(
            [sys.executable, str(cls.server), "--state", str(cls.state), "--port", str(cls.port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.base = f"http://127.0.0.1:{cls.port}"
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                if cls.get("/health").get("ok"):
                    break
            except Exception:
                time.sleep(0.05)
        else:
            raise RuntimeError("PAY-1 local app did not start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
        cls.tmp.cleanup()

    @classmethod
    def get(cls, path):
        with urlopen(cls.base + path, timeout=2) as response:
            body = response.read()
            if "text/html" in response.headers.get("Content-Type", ""):
                return body.decode()
            return json.loads(body)

    @classmethod
    def post(cls, path, obj):
        req = Request(cls.base + path, data=json.dumps(obj).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=2) as response:
            return json.loads(response.read())

    def setUp(self):
        self.post("/api/reset", {})

    def test_roles_have_normal_visible_recovery_and_separate_source_page(self):
        clerk = self.get("/case/clerk")
        supervisor = self.get("/case/supervisor")
        self.assertIn("point-in-time batch snapshots", clerk)
        self.assertIn("Refresh approved timecard", clerk)
        self.assertNotIn("Signed correction COR-W19-E08", clerk)
        self.assertIn("Signed correction COR-W19-E08", supervisor)

    def test_same_app_state_contract_rejects_stale_but_accepts_audited_reissue(self):
        self.post("/api/correction", {"actor": "B"})
        self.post("/api/payment", {"actor": "A", "hours_tenths": 80, "ui_observed_hours_tenths": 80})
        stale = self.get("/api/state")
        self.assertFalse(fx.evaluate_shared(stale)["success"])
        self.post("/api/void", {"actor": "A", "payment_id": "PAY-W19-E-08-01"})
        self.post("/api/payment", {"actor": "A", "hours_tenths": 60, "ui_observed_hours_tenths": 60})
        recovered = self.get("/api/state")
        self.assertTrue(fx.evaluate_shared(recovered)["success"], fx.evaluate_shared(recovered))

    def test_ma_id_isolated_clones_use_same_workspace_local_oracle(self):
        a = fx.fresh_state()
        b = fx.fresh_state()
        # Exercise app B transition against its own identically initialized clone via fixture function.
        fx.apply_signed_correction(b)
        self.post("/api/payment", {"actor": "A", "hours_tenths": 80})
        state_a = self.get("/api/state")
        state_b = b
        # The local app test process is itself an A clone; both clones have the same initial hash.
        self.assertTrue(fx.evaluate_isolated(state_a, state_b)["success"])

    def test_other_actor_cannot_perform_owned_mutation(self):
        req = Request(self.base + "/api/correction", data=json.dumps({"actor":"A"}).encode(),
                      headers={"Content-Type":"application/json"}, method="POST")
        with self.assertRaises(Exception):
            urlopen(req, timeout=2)


if __name__ == "__main__":
    unittest.main()
