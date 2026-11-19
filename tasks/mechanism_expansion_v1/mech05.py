from __future__ import annotations
import base64, re, shlex, xml.etree.ElementTree as ET
from pathlib import Path
from evaluation_examples.task_class import pg_common as pc

NAME = 'mech05'
TASK_VERSION = '0.1.2'
HOME = '/home/user'
WORK = f'{HOME}/Documents/MECH05'
ODT = f'{WORK}/access-review-draft.odt'
ASSETS = Path('/mnt/raid1/mjh/Projects/codesk-mechanism-expansion-20261118/assets')
ASSET_REL = 'mechanism_expansion_v1/mech05/access-review-draft.odt'
BASE_PARAS = [
 'Access review — Draft 18 November 2026',
 'Approval boundary: Pilot access is limited to two named reviewers.',
 'Escalation contact: Pending confirmation.',
 'Control text: Preserve exactly TRACE-ONLY-77.',
]
A_OLD = 'Pilot access is limited to two named reviewers.'
A_NEW = 'Pilot access is limited to five named reviewers.'
B_OLD = 'Pending confirmation.'
B_NEW = 'compliance-ops@example.org'
NS = {
 'office':'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
 'text':'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
 'xml':'http://www.w3.org/XML/1998/namespace',
}
_SETUP = set()

def _focus_script():
 q = shlex.quote('access-review-draft')
 return f'for i in $(seq 60); do wid=$(xdotool search --onlyvisible --name {q} 2>/dev/null | tail -1 || true); [ -n "$wid" ] && {{ xdotool windowactivate --sync "$wid"; exit 0; }}; sleep 1; done; exit 1'

def setup(sc, role):
 key = f"{getattr(sc, 'vm_ip', '')}:{getattr(sc, 'server_port', '')}"
 if key in _SETUP: return
 pc.upload(sc, [(ASSET_REL, ODT)])
 pc.sh(sc, f'mkdir -p {WORK}/baseline && cp {ODT} {WORK}/baseline/access-review-draft.odt')
 pc.sh(sc, f'setsid -f libreoffice --writer {shlex.quote(ODT)} >/tmp/mech05-writer.log 2>&1 < /dev/null')
 pc.sh(sc, _focus_script(), timeout=45)
 _SETUP.add(key)

def _read_guest_xml(env):
 code = ('import base64,zipfile,sys; z=zipfile.ZipFile(sys.argv[1]); '
         'print("MECH05STATE"+base64.b64encode(z.read("content.xml")).decode())')
 raw = pc.guest(env, f'python3 -c {shlex.quote(code)} {shlex.quote(ODT)}', timeout=90)
 m = re.search(r'MECH05STATE([A-Za-z0-9+/=]+)', raw)
 if not m: return {'read_error': raw[-1200:]}
 try: return {'odt': base64.b64decode(m.group(1))}
 except Exception as e: return {'read_error': f'{type(e).__name__}: {e}'}

def _content_state(xml_bytes):
 root = ET.fromstring(xml_bytes)
 t = lambda local: f"{{{NS['text']}}}{local}"
 office_text = root.find('.//office:text', NS)
 if office_text is None: return {'paragraphs': [], 'insertions': [], 'deletions': [], 'markers': 0}
 paras = []
 para_segments = []
 segments = []
 def walk_para(p):
  active = None
  pieces = []
  if p.text: pieces.append((p.text, active))
  for child in p:
   if child.tag == t('change-start'):
    active = child.get(t('change-id'))
   elif child.tag == t('change-end'):
    if child.text: pieces.append((child.text, active))
    active = None
   elif child.tag == t('change'):
    pass
   else:
    # Preserve ordinary inline spans; track-markers normally bracket sibling text.
    if child.text: pieces.append((child.text, active))
    for grand in child:
     if grand.text: pieces.append((grand.text, active))
     if grand.tail: pieces.append((grand.tail, active))
   if child.tail: pieces.append((child.tail, active))
  return pieces
 def document_paragraphs(node):
  for child in node:
   if child.tag == t('tracked-changes'):
    continue
   if child.tag == t('p'):
    yield child
   else:
    yield from document_paragraphs(child)
 for p in document_paragraphs(office_text):
  pieces = walk_para(p)
  paras.append(''.join(s for s, _ in pieces))
  para_segments.append(pieces)
  segments.extend((s, marker) for s, marker in pieces)
 region_kind = {}
 deleted = []
 for region in root.findall('.//text:tracked-changes/text:changed-region', NS):
  rid = region.get(t('id')) or region.get(f"{{{NS['xml']}}}id")
  ins = region.find('.//text:insertion', NS)
  dele = region.find('.//text:deletion', NS)
  if ins is not None: region_kind[rid] = 'insertion'
  if dele is not None:
   region_kind[rid] = 'deletion'
   deleted.append(''.join(''.join(p.itertext()) for p in dele.findall('.//text:p', NS)).strip())
 active_paras = [''.join(text for text, rid in pieces
                          if not rid or region_kind.get(rid) != 'deletion')
                 for pieces in para_segments]
 active_text = ''.join(text for text, rid in segments
                       if not rid or region_kind.get(rid) != 'deletion')
 inserts = []
 for text, rid in segments:
  if rid and region_kind.get(rid) == 'insertion': inserts.append(text)
 marker_ids = {rid for _, rid in segments if rid}
 return {'paragraphs': paras, 'active_paragraphs': active_paras,
         'insertions': inserts, 'deletions': deleted,
         'region_kind': region_kind, 'marker_ids': marker_ids,
         'markers': len(region_kind), 'active_text': active_text,
         'plain_text': ''.join(text for text, rid in segments if not rid)}

def evaluate_bytes(xml_bytes, role):
 try: state = _content_state(xml_bytes)
 except Exception as e: return {'score': 0.0, 'checks': {'odt_readable': False}, 'state': {'error': str(e)}}
 ps = state['active_paragraphs']
 expected_a = f'Approval boundary: {A_NEW}'
 expected_b = f'Escalation contact: {B_NEW}'
 checks = {'odt_readable': len(ps) >= 4,
           'control_line_preserved': len(ps) >= 4 and ps[3] == BASE_PARAS[3]}
 if role == 'A':
  checks['approval_text_correct'] = len(ps) >= 2 and ps[1] == expected_a
  checks['approval_change_tracked'] = (any(A_OLD in d for d in state['deletions']) and
      any(A_NEW in s for s in state['insertions']))
 else:
  checks['contact_text_correct'] = len(ps) >= 3 and ps[2] == expected_b
  checks['contact_is_plain_final_text'] = B_NEW in state['plain_text'] and not any(B_NEW in s for s in state['insertions'])
 state_out = {k: sorted(v) if isinstance(v, set) else v for k, v in state.items()}
 state_out['role'] = role
 state_out['mode_mismatch_evidence'] = {
  'a_expected_revision_missing': not (any(A_OLD in d for d in state['deletions']) and any(A_NEW in s for s in state['insertions'])),
  'b_unexpected_revision': any(B_NEW in s for s in state['insertions']),
 }
 return {'score': 1.0 if all(checks.values()) else 0.0, 'checks': checks,
         'state': state_out, 'mechanism_evidence': state_out['mode_mismatch_evidence']}

def evaluate(env, role):
 raw = _read_guest_xml(env)
 if 'read_error' in raw: return {'score': 0.0, 'checks': {'odt_readable': False}, 'state': raw}
 return evaluate_bytes(raw['odt'], role)

TASKS = {
 'A': 'In the open access-review draft, change the approval boundary so it reads exactly “Pilot access is limited to five named reviewers.” This wording is approved but still under review, so the replacement must remain an unaccepted tracked change. Before typing, open Edit > Track Changes > Record and inspect whether Record is checked: if it is unchecked, choose Record once to turn it on; if it is already checked, leave it on. Reopen the menu if needed to verify the check mark. Replace only the approval sentence, save, and do not accept or reject the revision.',
 'B': 'In the open access-review draft, replace “Pending confirmation.” with “compliance-ops@example.org” as final approved contact text. This contact line is finalized and must remain ordinary text, not a tracked revision. Before typing, open Edit > Track Changes > Record and inspect whether Record is checked: if it is checked, choose Record once to turn it off; if it is already unchecked, leave it off. Verify the check mark is absent, replace only the contact text, and save. Do not accept or reject anyone else’s revisions.',
}
