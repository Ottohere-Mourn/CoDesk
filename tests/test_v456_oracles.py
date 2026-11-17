import json, sqlite3, sys
from pathlib import Path
import pytest
ROOT=Path('/home/mjh/Projects/CoDesk-three-new-dualagent-cases-20261112')
sys.path.insert(0,str(ROOT/'tasks/paragui'))
from build_v456 import DATA, build
from pg_v456_oracle import checks
ASSETS=Path('/mnt/raid1/mjh/Projects/codesk-next3-20261112/assets')
def joint_state(case):
 c=DATA[case];out=[]
 for item in c['items']:
  x=dict(item);x.setdefault('data_a',{});x.setdefault('data_b',{})
  out.append({'id':x['id'],'kind':x['kind'],'facts':json.dumps(x.get('facts',{})),'data_a':json.dumps(x.get('data_a',{})),'data_b':json.dumps(x.get('data_b',{}))})
 by={x['id']:x for x in out}
 for iid,target in c['expected']['B'].items():by[iid]['data_b']=json.dumps(target)
 for iid,target in c['expected']['A'].items():
  data={k:v for k,v in target.items() if k!='allowed_rooms'}
  if case=='v4':
   room={'EV-311':'R-102','EV-312':'R-203','EV-313':'R-204','EV-314':'R-203','EV-315':'R-203'}[iid]
   data['room']=room
  by[iid]['data_a']=json.dumps(data)
 return {'items':out,'desk':{'active_id':'','active_panel':'A'}}
@pytest.mark.parametrize('case',['v4','v5','v6'])
def test_joint_positive_and_asset_rebuild(tmp_path,case):
 out=tmp_path/case;build(case,out)
 assert (out/f'app_{case}.py').is_file()
 con=sqlite3.connect(out/'seed.db')
 assert con.execute('select count(*) from items').fetchone()[0]==len(DATA[case]['items'])
 con.close()
 state=joint_state(case);expected=DATA[case]['expected']
 for panel in ('A','B'):
  checks_out,score=checks(state,expected,panel,case)
  assert score==1.0,checks_out
@pytest.mark.parametrize('case,iid,value,field,expected_score',[
 ('v4','EV-311','R-101','room',0.5),
 ('v5','EX-904','WRONG-REF','receipt_ref',0.5),
 ('v6','ST-407','E12','room',2/3)])
def test_shared_state_specific_failure_control(case,iid,value,field,expected_score):
 state=joint_state(case);state['items_by_id']={x['id']:x for x in state['items']}
 row=state['items_by_id'][iid];data=json.loads(row['data_'+('a' if case=='v4' else 'b')]);data[field]=value;row['data_'+('a' if case=='v4' else 'b')]=json.dumps(data)
 panel='A' if case=='v4' else 'B'
 _,score=checks(state,DATA[case]['expected'],panel,case)
 assert score==expected_score
def test_v4_common_open_capacity_after_closures():
 s=joint_state('v4');rows={r['id']:r for r in s['items']}
 open_rooms=[r for r in rows.values() if r['kind']=='B' and json.loads(r['data_b']).get('status')=='OPEN']
 assert {r['id'] for r in open_rooms}=={'R-102','R-202','R-203','R-204'}
 assert len(open_rooms)==4

@pytest.mark.parametrize('changes,expected_score',[
    ({'EV-311':{'room':'R-203'},'EV-314':{'room':'R-102'}},0.5),
    ({'EV-311':{'room':'R-203'},'EV-314':{'room':'R-203'}},0.0),
])
def test_v4_capacity_and_room_overlap_negatives(changes,expected_score):
    state=joint_state('v4')
    by={r['id']:r for r in state['items']}
    for iid,patch in changes.items():
        row=by[iid];data=json.loads(row['data_a']);data.update(patch);row['data_a']=json.dumps(data)
    _,score=checks(state,DATA['v4']['expected'],'A','v4')
    assert score==expected_score


@pytest.mark.parametrize('case',['v34','v35','v36','v37'])
def test_v34_v37_joint_positive_and_asset_rebuild(tmp_path,case):
 out=tmp_path/case;build(case,out)
 assert (out/f'app_{case}.py').is_file()
 con=sqlite3.connect(out/'seed.db')
 assert con.execute('select count(*) from items').fetchone()[0]==len(DATA[case]['items'])
 con.close()
 state=joint_state(case);expected=DATA[case]['expected']
 for panel in ('A','B'):
  checks_out,score=checks(state,expected,panel,case)
  assert score==1.0,checks_out

@pytest.mark.parametrize('case,panel',[('v34','A'),('v35','B'),('v36','A'),('v37','B')])
def test_v34_v37_oracle_rejects_wrong_record_value(case,panel):
 state=joint_state(case)
 iid=next(iter(DATA[case]['expected'][panel]))
 row=next(r for r in state['items'] if r['id']==iid)
 saved=json.loads(row['data_'+panel.lower()])
 key=next(iter(DATA[case]['expected'][panel][iid]))
 saved[key]='WRONG'
 row['data_'+panel.lower()]=json.dumps(saved)
 checks_out,score=checks(state,DATA[case]['expected'],panel,case)
 assert score==0.0,checks_out

@pytest.mark.parametrize('case',['v34','v35','v36','v37'])
def test_v34_v37_share_one_record_across_disjoint_panels(case):
 cfg=DATA[case]
 assert len(cfg['items'])==1
 assert cfg['items'][0]['kind']=='both'
 assert set(cfg['expected']['A'])==set(cfg['expected']['B'])=={cfg['items'][0]['id']}
 a={f['key'] for f in cfg['panels']['A']['fields']}
 b={f['key'] for f in cfg['panels']['B']['fields']}
 assert len(a)==len(b)==4
 assert not a & b

@pytest.mark.parametrize('case',['v38','v39','v40','v41','v42'])
def test_v38_v42_joint_positive_and_asset_rebuild(tmp_path,case):
 out=tmp_path/case;build(case,out)
 assert (out/f'app_{case}.py').is_file()
 con=sqlite3.connect(out/'seed.db')
 assert con.execute('select count(*) from items').fetchone()[0]==len(DATA[case]['items'])
 con.close()
 state=joint_state(case);expected=DATA[case]['expected']
 for panel in ('A','B'):
  checks_out,score=checks(state,expected,panel,case)
  assert score==1.0,checks_out

@pytest.mark.parametrize('case,panel',[('v38','A'),('v39','B'),('v40','A'),('v41','B'),('v42','A')])
def test_v38_v42_oracle_rejects_wrong_value(case,panel):
 state=joint_state(case)
 iid=next(iter(DATA[case]['expected'][panel]))
 row=next(r for r in state['items'] if r['id']==iid)
 saved=json.loads(row['data_'+panel.lower()])
 key=next(iter(DATA[case]['expected'][panel][iid]))
 saved[key]='WRONG'
 row['data_'+panel.lower()]=json.dumps(saved)
 checks_out,score=checks(state,DATA[case]['expected'],panel,case)
 assert score==0.0,checks_out

@pytest.mark.parametrize('case',['v38','v39','v40','v41','v42'])
def test_v38_v42_share_record_but_have_independent_panel_fields(case):
 cfg=DATA[case]
 assert len(cfg['items'])==1 and cfg['items'][0]['kind']=='both'
 iid=cfg['items'][0]['id']
 assert set(cfg['expected']['A'])==set(cfg['expected']['B'])=={iid}
 a={f['key'] for f in cfg['panels']['A']['fields']}
 b={f['key'] for f in cfg['panels']['B']['fields']}
 assert len(a)==len(b)==4 and not a & b

@pytest.mark.parametrize('case,panel,key,lower_value',[
    ('v39','A','defect','left rear brake-line leak'),
    ('v40','A','hazard','split limb over trail'),
    ('v41','A','device','aisle chair'),
])
def test_v38_v42_free_text_casefolds_only_targeted_semantic_fields(case,panel,key,lower_value):
 state=joint_state(case)
 iid=next(iter(DATA[case]['expected'][panel]))
 row=next(r for r in state['items'] if r['id']==iid)
 saved=json.loads(row['data_'+panel.lower()]);saved[key]=lower_value;row['data_'+panel.lower()]=json.dumps(saved)
 _,score=checks(state,DATA[case]['expected'],panel,case)
 assert score==1.0
 saved[key]='wrong unrelated phrase';row['data_'+panel.lower()]=json.dumps(saved)
 _,score=checks(state,DATA[case]['expected'],panel,case)
 assert score==0.0
