"""Create BC-02 workbook and optionally open it in LibreOffice Calc."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from xlsx_utils import build_workbook


def prepare(workspace: Path) -> Path:
    root = workspace.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return build_workbook(root / "q4_ops.xlsx")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path.home() / "workspace")
    parser.add_argument("--source-dir", type=Path, help="Staged Guest asset directory")
    parser.add_argument("--open-calc", action="store_true")
    args = parser.parse_args()
    workbook = prepare(args.workspace)
    if args.open_calc:
        subprocess.Popen(["libreoffice", "--calc", str(workbook)], start_new_session=True)
    print(f"Prepared BC-02 workbook at {workbook}")


if __name__ == "__main__":
    main()
