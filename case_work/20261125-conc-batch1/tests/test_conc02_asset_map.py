from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path

CASE_ROOT = Path(__file__).resolve().parents[1]
MODULE = CASE_ROOT / "CONC-02" / "integration" / "pg_conc02.py"


def _load_bridge():
    package = types.ModuleType("evaluation_examples")
    package.__path__ = []
    task_class = types.ModuleType("evaluation_examples.task_class")
    task_class.__path__ = []
    common = types.ModuleType("evaluation_examples.task_class.pg_common")
    common.HOME = "/home/user"
    common.upload = lambda setup, pairs: setattr(setup, "uploads", list(pairs))
    grader = types.ModuleType("evaluation_examples.task_class.conc02_grade")
    grader.grade = lambda *args, **kwargs: {}
    grader.load_expected = lambda *args, **kwargs: {}
    sys.modules.update({
        "evaluation_examples": package,
        "evaluation_examples.task_class": task_class,
        "evaluation_examples.task_class.pg_common": common,
        "evaluation_examples.task_class.conc02_grade": grader,
    })
    task_class.pg_common = common
    task_class.conc02_grade = grader
    spec = importlib.util.spec_from_file_location("conc02_test_bridge", MODULE)
    bridge = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(bridge)
    return bridge


class Conc02AssetMapTests(unittest.TestCase):
    def test_all_asset_uploads_strip_the_task_assets_case_prefix(self):
        bridge = _load_bridge()
        uploads = bridge._staged_uploads()
        self.assertEqual(len(uploads), len(bridge.FILES))
        for (source, _workspace_path), (staged_source, destination) in zip(bridge.FILES, uploads):
            self.assertEqual(source, staged_source)
            self.assertTrue(source.startswith("CONC-02/"))
            self.assertTrue(destination.startswith(bridge.ROOT + "/guest/"))
            self.assertEqual(destination, bridge.ROOT + "/" + source.removeprefix("CONC-02/"))

    def test_non_case_prefixed_path_is_rejected(self):
        bridge = _load_bridge()
        with self.assertRaises(ValueError):
            bridge._asset_destination("guest/in_a/finance_memo.txt")

    def test_setup_executes_copy_and_required_file_checks_with_check_enabled(self):
        bridge = _load_bridge()

        class FakeSetup:
            def execute(self, command, timeout=0, check=False):
                self.command = command
                self.timeout = timeout
                self.check = check

        setup = FakeSetup()
        bridge.setup(setup)
        self.assertEqual(setup.uploads, bridge._staged_uploads())
        self.assertEqual(setup.command[:2], ["bash", "-c"])
        self.assertTrue(setup.check)
        self.assertIn("set -e", setup.command[2])
        for path in (
            "/home/user/workspace/in_a/finance_memo.txt",
            "/home/user/workspace/in_a/chart_rev.png",
            "/home/user/workspace/in_b/launch_memo.txt",
            "/home/user/workspace/in_b/prod_side.png",
            "/home/user/workspace/out_a/Q4_Finance_Final.pptx",
            "/home/user/workspace/out_b/Product_Launch_Final.pptx",
        ):
            self.assertIn(f"test -s {path}", setup.command[2])


if __name__ == "__main__":
    unittest.main()
