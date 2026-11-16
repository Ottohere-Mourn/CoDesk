import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import pytest

from experiments.weavebench_writer_conflict import rules, saved_signals, version_review
from tasks.weavebench_writer_conflict.evaluate import body_sections, live_agreement, odt_structure, role_checks, toc_checks
from tasks.weavebench_writer_conflict.spec import NOTE, NS, PAIR, SEED_ID, build, section_rows, tag


@pytest.fixture
def prepared(tmp_path):
    for prefix, namespace in NS.items():
        ET.register_namespace(prefix, namespace)
    seed = tmp_path / 'seed'
    source = seed / 'tasks/workspace/DOC/task_2_heading_style_normalize/exec/report.odt'
    source.parent.mkdir(parents=True)
    prompt = seed / 'tasks/DOC' / (SEED_ID + '.md')
    prompt.parent.mkdir(parents=True)
    prompt.write_text('Seed task')
    root = ET.Element(tag('office', 'document-content'))
    body = ET.SubElement(ET.SubElement(root, tag('office', 'body')), tag('office', 'text'))
    wrong = {'sec_03', 'sec_05', 'sec_07', 'sec_09', 'sec_11', 'sec_13', 'sec_14'}
    for row in section_rows():
        heading = ET.SubElement(body, tag('text', 'p' if row['id'] in wrong else 'h'))
        if row['id'] not in wrong:
            heading.set(tag('text', 'outline-level'), '1')
        heading.text = row['original_title']
        ET.SubElement(body, tag('text', 'p')).text = 'Body for ' + row['id']
        ET.SubElement(body, tag('text', 'p'))
    with ZipFile(source, 'w') as archive:
        archive.writestr('mimetype', 'application/vnd.oasis.opendocument.text')
        archive.writestr('content.xml', ET.tostring(root))
    output = tmp_path / 'prepared'
    before = source.read_bytes()
    build(seed, output)
    assert source.read_bytes() == before
    return output


def test_seed_visible_content_and_seven_errors_preserved(prepared):
    source = prepared / 'private/original-report.odt'
    target = prepared / 'dataset/pairs' / PAIR / 'inputs/report.odt'
    with ZipFile(source) as archive:
        original = ET.fromstring(archive.read('content.xml'))
    with ZipFile(target) as archive:
        adapted = ET.fromstring(archive.read('content.xml'))
    original_body, adapted_body = (root.find('office:body/office:text', NS) for root in (original, adapted))
    assert [(''.join(node.itertext()), node.tag, node.attrib) for node in original_body] == [
        (''.join(node.itertext()), node.tag, node.attrib) for node in adapted_body]
    assert len(json.loads((prepared / 'private/baseline.json').read_text())['original_wrong_ids']) == 7
    structure = odt_structure(target)
    assert structure['bookmark_starts'] == structure['bookmark_ends'] == [row['id'] for row in section_rows()]


def test_inputs_have_no_answers_or_reference_code(prepared):
    inputs = prepared / 'dataset/pairs' / PAIR / 'inputs'
    assert not list(inputs.rglob('*.py'))
    assert not (inputs / 'baseline.json').exists()
    assert not list((inputs / 'results').iterdir())
    assert (inputs / 'review_note.txt').read_text().strip() == NOTE
    assert json.loads((prepared / 'provenance.json').read_text())['seed_id'] == SEED_ID


def test_builder_will_not_overwrite_existing_dataset(prepared, tmp_path):
    with pytest.raises(FileExistsError):
        build(tmp_path / 'seed', prepared)


def test_no_hidden_script_ban_or_enforced_serialization():
    text = rules()
    assert 'Four concurrent agents' in text and 'one already-open' in text
    assert 'including Python, UNO and XML' in text and 'harness supplies no lock' in text
    assert '2002' in text


def valid_state():
    heading_font = {'CharFontName': 'Liberation Sans', 'CharHeight': 18, 'CharWeight': 150,
        'CharColor': 0x1F3A5F, 'ParaKeepTogether': True}
    body_font = {'CharFontName': 'Liberation Sans', 'CharHeight': 11}
    sections = [{'id': row['id'], 'text': row['final_title'], 'bookmark_text': row['final_title'],
        'ParaStyleName': 'Heading 1', 'OutlineLevel': 1, 'BreakType': 'NONE',
        'ListLabelString': str(row['number']) + '. ', **heading_font} for row in section_rows()]
    paragraphs = []
    for section in sections:
        paragraphs.extend([section.copy(), {'text': 'Body for ' + section['id'], 'ParaStyleName': 'Text body', **body_font}])
        if section['id'] == 'sec_08':
            paragraphs.append({'text': NOTE, 'ParaStyleName': 'Text body', **body_font})
    return {'sections': sections, 'paragraphs': paragraphs, 'paragraph_styles': {'Heading 1': heading_font, 'Text body': body_font},
        'numbering': [{'HeadingStyleName': 'Heading 1', 'NumberingType': 4, 'StartWith': 1, 'Prefix': '', 'Suffix': '. '}],
        'page_styles': {'Standard': {'Width': 21000, 'Height': 29700, 'LeftMargin': 2000, 'RightMargin': 2000,
            'TopMargin': 2000, 'BottomMargin': 2000, 'IsLandscape': False, 'FooterIsOn': True,
            'footer_fields': [{'services': ['com.sun.star.text.TextField.PageNumber'], 'SubType': 'CURRENT', 'Offset': 0}]}},
        'indexes': [{'services': ['com.sun.star.text.ContentIndex'], 'Title': 'Contents', 'CreateFromOutline': True}]}


def checks(prepared, state):
    inputs = prepared / 'dataset/pairs' / PAIR / 'inputs'
    baseline = json.loads((prepared / 'private/baseline.json').read_text())
    (inputs / 'results/structure_audit.json').write_text(json.dumps({
        'wrong_section_ids': baseline['original_wrong_ids'], 'inspection': 'Inspected paragraph style and outline level.'}))
    return role_checks(state, odt_structure(inputs / 'report.odt'), baseline, inputs, 4)


def test_all_owned_edits_can_coexist(prepared):
    assert all(all(row.values()) for row in checks(prepared, valid_state()).values())


@pytest.mark.parametrize('mutation,role,key', [
    ('wrong_style', 'a', 'real_heading1'), ('reverted_title', 'b', 'final_titles'),
    ('no_native_numbering', 'b', 'native_chapter_rule'), ('missing_note', 'c', 'body_preserved_note_once'),
    ('wrong_font', 'c', 'heading_typography'), ('typed_page_number', 'c', 'footer_page_field')])
def test_regressions_are_attributed_to_owned_checks(prepared, mutation, role, key):
    state = valid_state()
    if mutation == 'wrong_style':
        state['sections'][2]['ParaStyleName'] = 'Text body'
    elif mutation == 'reverted_title':
        state['sections'][2]['text'] = 'Results'
    elif mutation == 'no_native_numbering':
        state['numbering'][0]['NumberingType'] = 5
    elif mutation == 'missing_note':
        state['paragraphs'] = [row for row in state['paragraphs'] if row['text'] != NOTE]
    elif mutation == 'wrong_font':
        state['sections'][5]['CharColor'] = 0
    else:
        state['page_styles']['Standard']['footer_fields'] = []
    assert checks(prepared, state)[role][key] is False


def test_body_note_belongs_to_limitations():
    groups = body_sections(valid_state())
    assert [row['text'] for row in groups['sec_08']] == ['Body for sec_08', NOTE]
    assert all(NOTE not in [row['text'] for row in rows] for identifier, rows in groups.items() if identifier != 'sec_08')


def test_toc_must_match_actual_pages_not_only_pdf_freshness():
    state = valid_state()
    headings = [str(row['number']) + '. ' + row['final_title'] for row in section_rows()]
    entries = [heading + '\t2' for heading in headings]
    structure = {'toc_count': 1, 'toc_rows': entries.copy()}
    pages = [['Contents', *[entry.replace('\t', ' ') for entry in entries]], headings]
    assert all(toc_checks(state, structure, pages)[0].values())
    structure['toc_rows'][4] = headings[4] + '\t3'
    assert not toc_checks(state, structure, pages)[0]['final_toc_entries_and_pages']


def test_live_must_be_saved_and_identical():
    saved = valid_state()
    live = {**copy.deepcopy(saved), 'url': 'file:///workspace/report.odt', 'writer_document_count': 1,
        'modified': False, 'modified_after': False}
    assert live_agreement(saved, live)
    live['modified'] = True
    assert not live_agreement(saved, live)
    live['modified'] = False
    live['sections'][0]['text'] = 'Unsaved change'
    assert not live_agreement(saved, live)


def test_missing_live_capture_is_not_a_pass():
    assert not live_agreement(valid_state(), {'error': 'disconnected'})


def test_temporary_document_does_not_invalidate_correct_canonical_state():
    saved = valid_state()
    live = {**copy.deepcopy(saved), 'url': 'file:///workspace/report.odt', 'writer_document_count': 2,
        'modified': False, 'modified_after': False}
    assert live_agreement(saved, live)


def test_native_numbering_roundtrip_metadata_is_not_a_false_live_mismatch():
    saved = valid_state()
    live = {**copy.deepcopy(saved), 'url': 'file:///workspace/report.odt', 'writer_document_count': 1,
        'modified': False, 'modified_after': False}
    saved['numbering'][0].update(ListFormat='%1%. ', ParentNumbering=1)
    live['numbering'][0]['ParentNumbering'] = 10
    assert live_agreement(saved, live)
    live['numbering'][0]['Suffix'] = ') '
    assert not live_agreement(saved, live)


def test_native_page_unit_rounding_is_allowed_but_wrong_margins_fail(prepared):
    state = valid_state()
    state['page_styles']['Standard']['Width'] = 21001
    assert checks(prepared, state)['c']['page_layout']
    state['page_styles']['Standard']['LeftMargin'] = 2500
    assert not checks(prepared, state)['c']['page_layout']


def test_saved_observer_reports_regression_not_best_snapshot(prepared, tmp_path):
    source = prepared / 'dataset/pairs' / PAIR / 'inputs/report.odt'
    assert not any(saved_signals(source).values())
    versions = tmp_path / 'shared/saved-versions'
    versions.mkdir(parents=True)
    with ZipFile(source) as archive:
        content = ET.fromstring(archive.read('content.xml'))
    for paragraph in content.find('office:body/office:text', NS):
        if paragraph.find('text:bookmark-start', NS) is not None:
            paragraph.tag = tag('text', 'h')
            paragraph.set(tag('text', 'outline-level'), '1')
    with ZipFile(versions / 'correct.odt', 'w') as archive:
        archive.writestr('content.xml', ET.tostring(content))
    (versions / 'stale.odt').write_bytes(source.read_bytes())
    (versions.parent / 'saved-versions.jsonl').write_text('\n'.join(json.dumps({'timestamp': timestamp, 'sha256': name})
        for timestamp, name in [(1, 'correct'), (2, 'stale')]))
    review = version_review(versions.parent)
    assert [row['signal'] for row in review['possible_regressions']] == ['a_outline_levels']
    assert not review['observations'][-1]['signals']['a_outline_levels']
