#!/usr/bin/env python3
import json, sqlite3, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=Path('/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112')
DATA=json.loads((HERE/'v456_data.json').read_text(encoding='utf-8'))
TEMPLATE=(HERE/'app_v456_template.py').read_text(encoding='utf-8')
def build(case_id,out):
 c=DATA[case_id];out=Path(out);out.mkdir(parents=True,exist_ok=True)
 (out/f'app_{case_id}.py').write_text(TEMPLATE.replace('__CONFIG__',repr(c)),encoding='utf-8')
 db=out/'seed.db'
 if db.exists():db.unlink()
 con=sqlite3.connect(db)
 con.executescript('CREATE TABLE items(id TEXT PRIMARY KEY,kind TEXT,name TEXT,details TEXT,clip_ref TEXT,facts TEXT,data_a TEXT,data_b TEXT,version INTEGER DEFAULT 0); CREATE TABLE desk(id INTEGER PRIMARY KEY CHECK(id=1),active_id TEXT,active_panel TEXT,rev INTEGER DEFAULT 0); CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT,item_id TEXT,panel TEXT,payload TEXT,ts TEXT DEFAULT CURRENT_TIMESTAMP);')
 for row in c['items']:
  con.execute('INSERT INTO items(id,kind,name,details,clip_ref,facts,data_a,data_b) VALUES(?,?,?,?,?,?,?,?)',(row['id'],row['kind'],row['name'],row['details'],row.get('clip_ref',''),json.dumps(row.get('facts',{}),ensure_ascii=False),json.dumps(row.get('data_a',{}),ensure_ascii=False),json.dumps(row.get('data_b',{}),ensure_ascii=False)))
 first=next(r['id'] for r in c['items'] if r['kind'] in ('A','both'))
 con.execute('INSERT INTO desk(id,active_id,active_panel,rev) VALUES(1,?,"A",0)',(first,))
 con.commit();con.close()
 (out/'expected.json').write_text(json.dumps(c['expected'],ensure_ascii=False,indent=2),encoding='utf-8')
 (out/'case.json').write_text(json.dumps({'title':c['title'],'subtitle':c['subtitle']},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
 if len(sys.argv)!=3:raise SystemExit('usage: build_v456.py v4|v5|v6|v7|v8|v9|v10|v11|v12 OUT')
 build(sys.argv[1],sys.argv[2])
