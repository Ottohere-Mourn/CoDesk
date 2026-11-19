from pathlib import Path
import os,sys
import hashlib,json
from odf.opendocument import OpenDocumentSpreadsheet
from odf.text import P
from odf.table import Table,TableRow,TableCell
from tasks.mechanism_expansion_v1.undo_family import CASES,TASK_VERSION
ASSET_ROOT=Path(sys.argv[1] if len(sys.argv)>1 else os.environ.get('PARAGUI_TASK_ASSETS', str(Path(__file__).resolve().parents[2] / 'task_assets')))
ROOT=ASSET_ROOT/'mechanism_expansion_v1'
for case,spec in CASES.items():
 dest=ROOT/case;dest.mkdir(parents=True,exist_ok=True)
 doc=OpenDocumentSpreadsheet();table=Table(name=spec['sheet'])
 for row in [spec['headers']]+spec['rows']:
  tr=TableRow()
  for value in row:
   cell=TableCell(valuetype='string')
   if value:cell.addElement(P(text=value))
   tr.addElement(cell)
  table.addElement(tr)
 doc.spreadsheet.addElement(table);path=dest/spec['file'];doc.save(str(path),addsuffix=False)
 manifest={'case_id':case.upper(),'task_version':TASK_VERSION,'application':'LibreOffice Calc','initial_gui_precondition':{'staged_cell':f'{chr(65+spec["a_temp_col"])}2','staged_value':spec['a_temp'],'unsaved_before_actor_start':True,'created_by_identical_setup_in_every_arm':True},'files':{path.name:hashlib.sha256(path.read_bytes()).hexdigest()}}
 (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(case,manifest['files'][path.name])
