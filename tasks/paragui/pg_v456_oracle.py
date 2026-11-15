import json,re
from decimal import Decimal,InvalidOperation
from datetime import datetime

def _obj(v):
    if isinstance(v, dict): return v
    try: return json.loads(v or '{}')
    except Exception: return {}

def _minutes(value):
    try:
        start, end = value.split('-', 1)
        def one(v):
            h, m = v.split(':', 1)
            return int(h) * 60 + int(m)
        a, b = one(start), one(end)
        return (a, b) if b > a else None
    except Exception:
        return None

def _amount(value):
    raw=str(value or '').replace(',','')
    match=re.search(r'-?\d+(?:\.\d+)?',raw)
    if not match:return None
    try:return Decimal(match.group(0))
    except InvalidOperation:return None

def _date_value(value):
    raw=str(value or '').strip()
    for fmt in ('%Y-%m-%d','%m/%d/%Y','%Y/%m/%d'):
        try:
            return datetime.strptime(raw,fmt).date()
        except ValueError:
            pass
    return None

def _field_matches(case_id,key,actual,target):
    if (case_id,key) in {('v23','reserve_amount'),('v27','recommended_award')}:
        got,want=_amount(actual),_amount(target)
        return got is not None and want is not None and got==want
    if (case_id,key)==('v27','scheduled_date'):
        got,want=_date_value(actual),_date_value(target)
        return got is not None and want is not None and got==want
    return str(actual)==str(target)

def checks(state, expected, panel, case_id):
    if not state or not isinstance(state.get('items'), list):
        return {'state_readable': False}, 0.0
    items = {r['id']: r for r in state['items']}
    wanted = expected.get(panel, {})
    out = {'state_readable': True}
    good = {}
    if case_id == 'v4' and panel == 'A':
        room_state = {}
        room_facts = {}
        for rid, row in items.items():
            if row.get('kind') == 'B':
                room_state[rid] = _obj(row.get('data_b')).get('status', 'OPEN')
                room_facts[rid] = _obj(row.get('facts'))
        bookings = {}
        for iid, target in wanted.items():
            row = items.get(iid)
            actual = _obj(row.get('data_a')) if row else {}
            facts = _obj(row.get('facts')) if row else {}
            exact = all(str(actual.get(k, '')) == str(v)
                        for k, v in target.items() if k != 'allowed_rooms')
            room = actual.get('room', '')
            rf = room_facts.get(room, {})
            allowed = set(facts.get('allowed_rooms', []))
            suitable = bool(
                room and room in allowed and room_state.get(room) == 'OPEN'
                and int(rf.get('capacity', 0)) >= int(facts.get('attendees', 10**9))
                and (not facts.get('stepfree') or bool(rf.get('stepfree')))
            )
            interval = _minutes(actual.get('time_slot', ''))
            good[iid] = bool(exact and suitable and interval)
            out[iid + '_exact_time_setup'] = bool(exact)
            out[iid + '_room_open_suitable'] = suitable
            out[iid + '_valid_time_slot'] = bool(interval)
            if room and interval:
                bookings.setdefault(room, []).append((iid, interval))
        for room, rows in bookings.items():
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    a, b = rows[i], rows[j]
                    if max(a[1][0], b[1][0]) < min(a[1][1], b[1][1]):
                        good[a[0]] = False
                        good[b[0]] = False
                        out[a[0] + '_no_room_conflict'] = False
                        out[b[0] + '_no_room_conflict'] = False
    else:
        for iid, target in wanted.items():
            row = items.get(iid)
            actual = _obj(row.get('data_' + panel.lower())) if row else {}
            ok = all(_field_matches(case_id,k,actual.get(k,''),v) for k,v in target.items())
            good[iid] = bool(ok)
            out[iid + '_exact'] = bool(ok)
    passed = sum(bool(v) for v in good.values())
    out['records_correct'] = f'{passed}/{len(wanted)}'
    return out, passed / len(wanted) if wanted else 0.0
