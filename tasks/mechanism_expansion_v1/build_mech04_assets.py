from pathlib import Path
import hashlib,json
from odf.opendocument import OpenDocumentSpreadsheet
from odf.text import P
from odf.table import Table,TableRow,TableCell
from tasks.mechanism_expansion_v1.mech04 import BASE
DEST=Path("/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets/mechanism_expansion_v1/mech04")
DEST.mkdir(parents=True,exist_ok=True)
doc=OpenDocumentSpreadsheet(); table=Table(name="QC Handoff Log")
for row in BASE:
 tr=TableRow()
 for value in row:
  cell=TableCell(valuetype="string")
  if value:cell.addElement(P(text=value))
  tr.addElement(cell)
 table.addElement(tr)
doc.spreadsheet.addElement(table)
path=DEST/"range-drift-log.ods";doc.save(str(path),addsuffix=False)
manifest={"case_id":"MECH-04","task_version":"0.1.0","files":{"range-drift-log.ods":hashlib.sha256(path.read_bytes()).hexdigest()}}
(DEST/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(json.dumps({"path":str(path),"sha256":manifest["files"]["range-drift-log.ods"],"rows":len(BASE)},indent=2))
