from tasks.mechanism_expansion_v1 import mech02

def ods_xml(rows):
    parts=[]
    for row in rows:
        cells=[]
        for value in row:
            if value:
                esc=str(value).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                cells.append(f'<table:table-cell office:value-type="string"><text:p>{esc}</text:p></table:table-cell>')
            else:
                cells.append('<table:table-cell/>')
        parts.append('<table:table-row>'+''.join(cells)+'</table:table-row>')
    return ('''<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
      xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
      xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
      <office:body><office:spreadsheet><table:table>''' + ''.join(parts) +
      '''</table:table></office:spreadsheet></office:body></office:document-content>''').encode()

def final_rows():
    rows=[r.copy() for r in mech02.BASE]
    rows[1][3]="Verified"
    rows[2][4]="427"
    rows[2][5]="JL"
    return rows

def test_parser_preserves_row_order_and_blank_cells():
    rows=mech02._ods_rows(ods_xml(mech02.BASE))
    assert rows==mech02.BASE
    assert mech02._state(rows)["row_order"]==[r[0] for r in mech02.BASE_ROWS]

def test_each_actor_passes_independently(monkeypatch):
    data=ods_xml(final_rows())
    monkeypatch.setattr(mech02,"_read_guest_xml",lambda env:{"ods":data})
    assert mech02.evaluate(None,"A")["score"]==1.0
    assert mech02.evaluate(None,"B")["score"]==1.0

def test_global_undo_interleaving_can_break_b_but_oracle_catches_it(monkeypatch):
    rows=final_rows()
    rows[2][5]=""  # A's single undo removed B's last cell edit.
    data=ods_xml(rows)
    monkeypatch.setattr(mech02,"_read_guest_xml",lambda env:{"ods":data})
    a=mech02.evaluate(None,"A")
    b=mech02.evaluate(None,"B")
    assert a["score"]==1.0
    assert b["score"]==0.0
    assert b["checks"]["b_count_427"] and not b["checks"]["b_verifier_jl"]

def test_unrestored_sort_fails_a_even_when_b_values_survive(monkeypatch):
    rows=final_rows()
    rows[1],rows[2]=rows[2],rows[1]
    data=ods_xml(rows)
    monkeypatch.setattr(mech02,"_read_guest_xml",lambda env:{"ods":data})
    assert mech02.evaluate(None,"A")["score"]==0.0
    assert mech02.evaluate(None,"A")["checks"]["original_order_restored"] is False



def test_parser_pads_ods_omitted_trailing_empty_cells():
    compressed=[r.copy() for r in mech02.BASE]
    compressed=[row[:max((i+1 for i,v in enumerate(row) if v),default=1)] for row in compressed]
    rows=mech02._ods_rows(ods_xml(compressed))
    assert rows==mech02.BASE
    assert all(len(row)==len(mech02.HEADERS) for row in rows)
