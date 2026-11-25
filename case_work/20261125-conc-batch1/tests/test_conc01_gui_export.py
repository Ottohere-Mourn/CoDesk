from __future__ import annotations

import base64
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

CASE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE_ROOT / "CONC-01" / "integration"))
import service as conc01_service


def _png(width: int, height: int, color=(0, 191, 165, 255)) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    pixel = bytes(color)
    row = b"\x00" + pixel * width
    raw = row * height
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))


class Conc01GuiExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_state = conc01_service.STATE
        self.old_lock = conc01_service.STATE_LOCK
        self.old_workspace = conc01_service.WORKSPACE
        conc01_service.STATE = self.root / "state.json"
        conc01_service.STATE_LOCK = self.root / "state.lock"
        conc01_service.WORKSPACE = self.root / "workspace"
        conc01_service.update_state(lambda state: None)

    def tearDown(self):
        conc01_service.STATE = self.old_state
        conc01_service.STATE_LOCK = self.old_lock
        conc01_service.WORKSPACE = self.old_workspace
        self.temp.cleanup()

    def test_actor_a_report_is_built_from_recorded_gui_checks(self):
        rows = [
            {"band": "mobile", "width": 375, "badge_code": "111111", "bug_element_ids": ["btn-express-pay"]},
            {"band": "tablet", "width": 768, "badge_code": "222222", "bug_element_ids": ["cart-total", "promo-banner"]},
            {"band": "desktop", "width": 1440, "badge_code": "333333", "bug_element_ids": []},
        ]
        conc01_service.update_state(lambda state: state["a_checks"].extend(rows))
        report = conc01_service._build_a_report(conc01_service.read_state())
        self.assertEqual(report["mobile"], {"has_bug": True, "bug_element_id": "btn-express-pay", "badge_code": "111111"})
        self.assertEqual(report["tablet"]["bug_element_id"], "cart-total, promo-banner")
        self.assertEqual(report["desktop"]["bug_element_id"], "NONE")

    def test_actor_b_report_requires_and_exports_all_gui_hover_values(self):
        state = conc01_service.fresh_state()
        state["b_hovers"] = [{"tab": tab, "peak": peak, "width": 1920, "height": 1080}
                             for tab in conc01_service.TABS for peak in ("peak_a", "peak_b")]
        report = conc01_service._build_b_report(state)
        self.assertEqual(set(report), set(conc01_service.TABS))
        self.assertEqual(report["tab_1"], state["peaks"]["tab_1"])
        with self.assertRaises(ValueError):
            conc01_service._build_b_report({"b_hovers": [], "peaks": state["peaks"]})

    def test_gui_png_export_uses_fixed_actor_path_and_viewport_gate(self):
        conc01_service.update_state(lambda state: state["a_checks"].append(
            {"band": "mobile", "width": 375, "height": 812, "badge_code": "123456", "bug_element_ids": []}))
        png = _png(375, 812)
        data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        name, width, height = conc01_service._save_browser_png("a", "", {"band": "mobile", "png_data": data_url})
        saved = conc01_service.WORKSPACE / "out_a" / "qa_375.png"
        self.assertEqual((name, width, height), ("qa_375.png", 375, 812))
        self.assertEqual(saved.read_bytes(), png)
        with self.assertRaises(ValueError):
            conc01_service._save_browser_png("a", "", {"band": "desktop", "png_data": data_url})

    def test_pages_expose_browser_gui_export_controls(self):
        self.assertIn("saveViewportEvidence", conc01_service.a_html())
        self.assertIn("Export QA report JSON", conc01_service.a_html())
        self.assertIn("saveTabEvidence", conc01_service.b_html())
        self.assertIn("Export telemetry JSON", conc01_service.b_html())


if __name__ == "__main__":
    unittest.main()
