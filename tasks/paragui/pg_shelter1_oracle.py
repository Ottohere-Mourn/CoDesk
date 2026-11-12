"""Arm-agnostic pure oracles for SHELTER-INTAKE1; no guest, CLI, or arm label required."""

def placement_checks(st, exp):
    if not st: return {'state':'unreadable'},0.0
    want=exp['families']; rooms=exp['rooms']; assignments={}
    for row in st['assignments']: assignments.setdefault(row['family_id'],[]).append(row)
    current={r['id']:r for r in st['rooms']}; checks={}; per=[]; loads={}
    for fid,f in want.items():
        rows=assignments.get(fid,[]); one=len(rows)==1; row=rows[0] if one else {}
        room=rooms.get(row.get('room_id'),{}); cur=current.get(row.get('room_id'),{})
        occ=row.get('occupants'); fit=bool(room) and cur.get('status')=='Open' and isinstance(occ,int) and occ<=cur.get('capacity',-1)
        access=not f['accessible'] or bool(room.get('accessible'))
        companion=not f['companion'] or bool(room.get('companion'))
        note_present=bool(str(row.get('note') or '').strip())
        ok=one and fit and access and companion and row.get('status')=='draft' and occ==f['occupants'] and note_present
        per.append(bool(ok)); checks[fid]={'one_assignment':one,'room':row.get('room_id'),'open_and_fits':fit,'accessible':access,'companion':companion,'occupants_correct':occ==f['occupants'],'placement_note_present':note_present}
        if row.get('room_id'): loads[row['room_id']]=loads.get(row['room_id'],0)+int(occ or 0)
    cap={r['id']:r['capacity'] for r in st['rooms']}; capacity_ok=all(n<=cap.get(rid,0) for rid,n in loads.items())
    checks['all_four_households_correct']=sum(per)==len(want); checks['no_room_over_capacity']=capacity_ok
    return checks,(sum(per)/max(1,len(want))+float(capacity_ok))/2

def facilities_checks(st, exp):
    if not st: return {'state':'unreadable'},0.0
    want=exp['required_closure']; room=next((r for r in st['rooms'] if r['id']==want['room']),{})
    closures=[r for r in st['closures'] if r['room_id']==want['room'] and r['inspection_id']==want['inspection'] and r['reason']==want['reason'] and r['status']=='Closed']
    work=[r for r in st['work_orders'] if r['room_id']==want['room'] and r['inspection_id']==want['inspection'] and r['priority']=='High' and r['status']=='Open' and 'before reopening' in r['note'].lower()]
    checks={'room_closed_and_zero_capacity':room.get('status')=='Closed' and room.get('capacity')==0,'exact_inspection_closure':len(closures)==1,'high_priority_work_order':len(work)==1}
    return checks,sum(checks.values())/len(checks)
