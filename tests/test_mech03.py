import xml.etree.ElementTree as ET
from tasks.mechanism_expansion_v1 import mech03

def ods_xml(target=""):
    rows = []
    for ri,row in enumerate(mech03.BASE_GRID):
        cells=[]
        for ci,val in enumerate(row):
            if ri==11 and ci==3 and target:
                cell=f'<table:table-cell office:value-type="float" office:value="{target}"/>'
            elif val:
                escaped=val.replace("&","&amp;").replace("<","&lt;")
                cell=f'<table:table-cell office:value-type="string"><text:p>{escaped}</text:p></table:table-cell>'
            else:
                cell='<table:table-cell/>'
            cells.append(cell)
        rows.append('<table:table-row>'+''.join(cells)+'</table:table-row>')
    return ('''<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
      xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
      xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
      <office:body><office:spreadsheet><table:table>''' + ''.join(rows) +
      '''</table:table></office:spreadsheet></office:body></office:document-content>''').encode()

def odt_xml(paragraph):
    esc=paragraph.replace("&","&amp;").replace("<","&lt;")
    return ('''<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
      xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
      <office:body><office:text><text:p>''' + esc +
      '''</text:p></office:text></office:body></office:document-content>''').encode()

def test_readers_parse_odf_content():
    assert mech03._ods_values(ods_xml("1250.00"))[-1][3] == "1250.00"
    assert mech03._odt_paragraphs(odt_xml(mech03.EXPECTED_REPLY)) == [mech03.EXPECTED_REPLY]
    assert mech03._matches_credit("1250")
    assert not mech03._matches_credit("125.00")

def test_pair_scores_own_document_independently(monkeypatch):
    # In a shared Guest each actor's correct edit must not be scored as the other actor's collateral mutation.
    monkeypatch.setattr(mech03,"_read_guest_xml",
        lambda env:{"ods":ods_xml("1250.00"),"odt":odt_xml(mech03.EXPECTED_REPLY)})
    assert mech03.evaluate(None,"A")["score"] == 1.0
    assert mech03.evaluate(None,"B")["score"] == 1.0

def test_focus_misroute_wrongly_overwriting_writer_fails_both_goals(monkeypatch):
    monkeypatch.setattr(mech03,"_read_guest_xml",
        lambda env:{"ods":ods_xml(""),"odt":odt_xml(mech03.EXPECTED_REPLY+"1250.00")})
    assert mech03.evaluate(None,"A")["score"] == 0.0
    assert mech03.evaluate(None,"B")["score"] == 0.0
