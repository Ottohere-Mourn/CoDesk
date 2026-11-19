"""Build immutable ODF fixtures for MECH-03 focus-routing candidate."""
from pathlib import Path
import hashlib, json
from odf.opendocument import OpenDocumentText, OpenDocumentSpreadsheet
from odf.text import P
from odf.table import Table, TableRow, TableCell

ROOT = Path(__file__).resolve().parents[2]
DEST = Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets/mechanism_expansion_v1/mech03")
DEST.mkdir(parents=True, exist_ok=True)

def text_doc(path):
    doc = OpenDocumentText()
    doc.text.addElement(P(text="Draft response pending."))
    doc.save(str(path), addsuffix=False)

def sheet_doc(path):
    doc = OpenDocumentSpreadsheet()
    table = Table(name="Service Adjustments")
    rows = [
      ["Service ID", "Customer", "Adjustment status", "Approved credit"],
      ["SR-2001", "Maple Grove", "Closed", "0.00"],
      ["SR-2004", "Cedar Works", "Closed", "0.00"],
      ["SR-2010", "North Shore", "Reviewed", "0.00"],
      ["SR-2016", "Blue Peak", "Reviewed", "0.00"],
      ["SR-2022", "Orchard Labs", "Pending", "0.00"],
      ["SR-2029", "Westlake Clinic", "Pending", "0.00"],
      ["SR-2032", "Brightline", "Approved", "0.00"],
      ["SR-2038", "Hawthorne", "Approved", "0.00"],
      ["SR-2047", "Fairview Co-op", "Pending", "0.00"],
      ["SR-2055", "Lakeside Motors", "Reviewed", "0.00"],
      ["SR-2081", "Kestrel Supplies", "Approved", ""],
    ]
    for row in rows:
        tr = TableRow()
        for value in row:
            cell = TableCell(valuetype="string")
            if value:
                cell.addElement(P(text=value))
            tr.addElement(cell)
        table.addElement(tr)
    doc.spreadsheet.addElement(table)
    doc.save(str(path), addsuffix=False)

text_doc(DEST / "customer-response.odt")
sheet_doc(DEST / "service-adjustments.ods")
manifest = {"case_id":"MECH-03","task_version":"0.2.0","files":{}}
for name in ("customer-response.odt","service-adjustments.ods"):
    manifest["files"][name] = hashlib.sha256((DEST/name).read_bytes()).hexdigest()
(DEST/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(json.dumps({"assets":str(DEST),"manifest":manifest},indent=2))
