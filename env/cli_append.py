"""CLI actor operation: append one row to the shared CSV."""
import argparse
import csv
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("--csv", type=Path, required=True)
parser.add_argument("--actor", required=True)
parser.add_argument("--value", required=True)
args = parser.parse_args()
with args.csv.open(newline="", encoding="utf-8") as stream:
    rows = list(csv.DictReader(stream))
row_id = f"C{sum(row['actor'] == args.actor for row in rows) + 1}"
rows.append({"id": row_id, "actor": args.actor, "value": args.value})
with args.csv.open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=("id", "actor", "value"), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    stream.flush()
print(f"appended {row_id}")
