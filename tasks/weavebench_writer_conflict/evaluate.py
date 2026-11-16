"""Private deterministic grading of saved artifacts and a pre-stop live snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from tasks.weavebench_writer_conflict.observer import connect, snapshot
from tasks.weavebench_writer_conflict.spec import NOTE, NS, section_rows, write_json


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def property_value(name, item):
    import uno
    result = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
    result.Name, result.Value = name, item
    return result


def saved_snapshot(workspace, output):
    import uno
    with tempfile.TemporaryDirectory(prefix='writer-private-eval-') as profile:
        log = (output / 'libreoffice.log').open('wb')
        process = subprocess.Popen(['libreoffice', '-env:UserInstallation=' + Path(profile).as_uri(),
            '--headless', '--norestore', '--nologo', '--nofirststartwizard',
            '--accept=socket,host=127.0.0.1,port=2003;urp;StarOffice.ServiceManager'], stdout=log, stderr=log)
        desktop, document = None, None
        try:
            _, desktop = connect(2003)
            document = desktop.loadComponentFromURL(uno.systemPathToFileUrl(str(workspace / 'report.odt')),
                '_blank', 0, (property_value('Hidden', True), property_value('ReadOnly', True),
                    property_value('UpdateDocMode', uno.getConstantByName('com.sun.star.document.UpdateDocMode.NO_UPDATE')),
                    property_value('MacroExecutionMode', uno.getConstantByName('com.sun.star.document.MacroExecMode.NEVER_EXECUTE'))))
            if document is None:
                raise RuntimeError('Cannot load submitted ODT')
            state = snapshot(document)
            document.storeToURL(uno.systemPathToFileUrl(str(output / 'native-export.pdf')),
                (property_value('FilterName', 'writer_pdf_Export'), property_value('Overwrite', True)))
            return state
        finally:
            if document is not None:
                document.close(True)
            if desktop is not None:
                desktop.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            log.close()


def odt_structure(path):
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read('content.xml'))
    starts = root.findall('.//text:bookmark-start', NS)
    ends = root.findall('.//text:bookmark-end', NS)
    name = '{' + NS['text'] + '}name'
    toc = root.findall('.//text:table-of-content', NS)
    return {'bookmark_starts': [node.get(name) for node in starts if node.get(name, '').startswith('sec_')],
        'bookmark_ends': [node.get(name) for node in ends if node.get(name, '').startswith('sec_')],
        'toc_count': len(toc), 'toc_rows': [paragraph_text(node)
            for index in toc for body in index.findall('text:index-body', NS) for node in body.findall('text:p', NS)]}


def paragraph_text(node):
    result = node.text or ''
    for child in node:
        local = child.tag.rsplit('}', 1)[-1]
        if local == 'tab':
            result += '\t'
        elif local == 's':
            result += ' ' * int(child.get('{' + NS['text'] + '}c', '1'))
        else:
            result += paragraph_text(child)
        result += child.tail or ''
    return result


def body_sections(state):
    anchors = {row['text']: row['id'] for row in state['sections']}
    result, current = {}, None
    for paragraph in state['paragraphs']:
        if paragraph['text'] in anchors:
            current = anchors[paragraph['text']]
            result[current] = []
        elif current is not None and paragraph['text'].strip():
            result[current].append(paragraph)
    return result


def role_checks(state, structure, baseline, workspace, arabic_type):
    expected = section_rows()
    identifiers = [row['id'] for row in expected]
    sections = {row['id']: row for row in state['sections']}
    complete = len(state['sections']) == len(expected) and set(sections) == set(identifiers)
    heading = state['paragraph_styles'].get('Heading 1', {})
    body = state['paragraph_styles'].get('Text body', {})
    numbering = state['numbering'][0] if state['numbering'] else {}
    groups = body_sections(state)
    try:
        audit = json.loads((workspace / 'results/structure_audit.json').read_text())
        correct_audit = (sorted(audit['wrong_section_ids']) == sorted(baseline['original_wrong_ids'])
            and isinstance(audit['inspection'], str) and bool(audit['inspection'].strip()))
    except (OSError, ValueError, KeyError, TypeError):
        correct_audit = False
    pages = state['page_styles']
    def heading_font(row):
        return (row.get('CharFontName') == 'Liberation Sans' and row.get('CharHeight') == 18
            and row.get('CharWeight') == 150 and row.get('CharColor') == 0x1F3A5F
            and row.get('ParaKeepTogether') is True)
    def body_font(row):
        return row.get('CharFontName') == 'Liberation Sans' and row.get('CharHeight') == 11
    expected_body = {row['id']: [text for text in row['body'] if text.strip()] + ([NOTE] if row['id'] == 'sec_08' else [])
        for row in baseline['sections']}
    return {'a': {
        'bookmarks_order': complete and structure['bookmark_starts'] == identifiers and structure['bookmark_ends'] == identifiers,
        'real_heading1': complete and all(row['ParaStyleName'] == 'Heading 1' and row['OutlineLevel'] == 1 for row in sections.values()),
        'initial_style_audit': correct_audit},
        'b': {
            'final_titles': complete and all(sections[row['id']]['text'] == row['final_title']
                and sections[row['id']]['bookmark_text'] == row['final_title'] for row in expected),
            'native_chapter_rule': all(numbering.get(key) == item for key, item in {
                'HeadingStyleName': 'Heading 1', 'NumberingType': arabic_type, 'StartWith': 1, 'Prefix': '', 'Suffix': '. '}.items()),
            'rendered_number_sequence': complete and all(sections[row['id']].get('ListLabelString', '').strip() == str(row['number']) + '.' for row in expected)},
        'c': {
            'heading_typography': heading_font(heading) and complete and all(heading_font(row) for row in sections.values()),
            'body_typography': body_font(body) and set(groups) == set(identifiers) and all(
                row['ParaStyleName'] == 'Text body' and body_font(row) for rows in groups.values() for row in rows),
            'page_layout': len(pages) == 1 and all(row.get('IsLandscape') is False and all(
                isinstance(row.get(key), (int, float)) and abs(row[key] - item) <= 2 for key, item in {
                'Width': 21000, 'Height': 29700, 'LeftMargin': 2000, 'RightMargin': 2000,
                'TopMargin': 2000, 'BottomMargin': 2000}.items()) for row in pages.values()),
            'footer_page_field': bool(pages) and all(row.get('FooterIsOn') is True and any(
                'com.sun.star.text.TextField.PageNumber' in field['services'] and field.get('SubType') == 'CURRENT'
                and field.get('Offset') == 0 for field in row['footer_fields']) for row in pages.values()),
            'body_preserved_note_once': {identifier: [row['text'] for row in rows] for identifier, rows in groups.items()} == expected_body,
            'no_chapter_page_breaks': complete and all(row.get('BreakType') == 'NONE' for identifier, row in sections.items() if identifier != 'sec_01')}}


def pdf_pages(path):
    result = subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True, capture_output=True, timeout=30)
    pages = result.stdout.decode('utf-8').split('\f')
    if pages and not pages[-1].strip():
        pages.pop()
    return [[' '.join(line.split()) for line in page.splitlines() if line.strip()] for page in pages]


def toc_checks(state, structure, pages):
    expected = section_rows()
    indexes = state['indexes']
    native_toc = len(indexes) == 1 and structure['toc_count'] == 1 and (
        'com.sun.star.text.ContentIndex' in indexes[0]['services'] and indexes[0]['Title'] == 'Contents'
        and indexes[0]['CreateFromOutline'] is True)
    actual_pages, toc_pages = {}, {}
    for row in expected:
        heading = str(row['number']) + '. ' + row['final_title']
        actual_pages[row['id']] = [index + 1 for index, lines in enumerate(pages) for line in lines if line == heading]
        pattern = re.compile(r'^' + re.escape(heading) + r'[\s.·…]+(\d+)\s*$')
        matches = [pattern.fullmatch(' '.join(text.split())) for text in structure['toc_rows']]
        toc_pages[row['id']] = [int(match.group(1)) for match in matches if match]
    valid_headings = all(len(actual_pages[row['id']]) == 1 for row in expected)
    valid_pages = valid_headings and all(toc_pages[row['id']] == actual_pages[row['id']] for row in expected)
    full_first_page = bool(pages) and 'Contents' in pages[0] and all(any(re.fullmatch(
        re.escape(str(row['number']) + '. ' + row['final_title']) + r'[\s.·…]+\d+', line)
        for line in pages[0]) for row in expected)
    return {'native_toc': native_toc,
        'final_toc_entries_and_pages': valid_pages and len(structure['toc_rows']) == 15,
        'toc_page1_body_page2': full_first_page and valid_headings and actual_pages['sec_01'] == [2]
            and all(page[0] >= 2 for page in actual_pages.values())}, {'heading_pages': actual_pages, 'toc_pages': toc_pages}


def compare_pdf(submitted, native, output):
    from PIL import Image, ImageChops, ImageStat
    actual_pages, reference_pages = pdf_pages(submitted), pdf_pages(native)
    def geometry(path):
        response = subprocess.run(['pdftotext', '-bbox', str(path), '-'], check=True, capture_output=True, timeout=30)
        return [(float(node.get('width')), float(node.get('height'))) for node in ET.fromstring(response.stdout).iter()
            if node.tag.rsplit('}', 1)[-1] == 'page']
    actual_sizes, reference_sizes = geometry(submitted), geometry(native)
    details = {'page_text_equal': actual_pages == reference_pages, 'page_count_equal': len(actual_pages) == len(reference_pages),
        'page_sizes_equal': actual_sizes == reference_sizes, 'submitted_page_sizes_pt': actual_sizes,
        'reference_page_sizes_pt': reference_sizes, 'pages': []}
    for name, path in (('submitted', submitted), ('reference', native)):
        subprocess.run(['pdftoppm', '-r', '72', '-png', str(path), str(output / name)], check=True, capture_output=True, timeout=90)
    actual = sorted(output.glob('submitted-*.png'), key=lambda path: int(path.stem.rsplit('-', 1)[1]))
    reference = sorted(output.glob('reference-*.png'), key=lambda path: int(path.stem.rsplit('-', 1)[1]))
    for actual_path, reference_path in zip(actual, reference):
        with Image.open(actual_path) as actual_image, Image.open(reference_path) as reference_image:
            same_size = actual_image.size == reference_image.size
            mean, fraction = None, None
            if same_size:
                difference = ImageChops.difference(actual_image.convert('RGB'), reference_image.convert('RGB'))
                mean = sum(ImageStat.Stat(difference).mean) / 3
                maximum = ImageChops.lighter(ImageChops.lighter(*difference.split()[:2]), difference.split()[2])
                histogram = maximum.histogram()
                fraction = sum(histogram[9:]) / sum(histogram)
            details['pages'].append({'same_size': same_size, 'mean_channel_difference': mean, 'fraction_over_8': fraction,
                'pass': same_size and mean <= .1 and fraction <= .001})
    details['pass'] = (details['page_text_equal'] and details['page_count_equal'] and details['page_sizes_equal'] and len(actual) == len(reference)
        and len(actual) > 0 and all(row['pass'] for row in details['pages']))
    return details


def live_agreement(saved, live):
    if 'error' in live:
        return False
    keys = ('paragraphs', 'sections', 'paragraph_styles', 'page_styles', 'indexes')
    numbering_keys = ('HeadingStyleName', 'NumberingType', 'StartWith', 'Prefix', 'Suffix')
    numbering_matches = bool(saved['numbering']) and bool(live.get('numbering')) and all(
        saved['numbering'][0].get(key) == live['numbering'][0].get(key) for key in numbering_keys)
    return (live.get('url') == 'file:///workspace/report.odt'
        and live.get('modified') is False and live.get('modified_after') is False
        and numbering_matches and all(saved[key] == live.get(key) for key in keys))


def grade(workspace, baseline, live, output):
    import uno
    output.mkdir(parents=True, exist_ok=True)
    original_hash = sha256(workspace / 'report.odt')
    state = saved_snapshot(workspace, output)
    write_json(output / 'saved-state.json', state)
    structure = odt_structure(workspace / 'report.odt')
    checks = role_checks(state, structure, baseline, workspace, uno.getConstantByName('com.sun.star.style.NumberingType.ARABIC'))
    pdf = workspace / 'results/report.pdf'
    pages = pdf_pages(pdf) if pdf.is_file() else []
    checks['d'], toc_details = toc_checks(state, structure, pages)
    try:
        receipt = json.loads((workspace / 'results/publication.json').read_text())
        checks['d']['publication_receipt'] = (receipt.get('odt_sha256') == original_hash
            and pdf.is_file() and receipt.get('pdf_sha256') == sha256(pdf)
            and receipt.get('section_ids') == [row['id'] for row in section_rows()])
    except (OSError, ValueError, TypeError, AttributeError):
        checks['d']['publication_receipt'] = False
    comparison = compare_pdf(pdf, output / 'native-export.pdf', output) if pdf.is_file() else {'pass': False, 'reason': 'PDF absent'}
    joint = {'live_saved_agreement': live_agreement(state, live), 'pdf_matches_native_export': comparison['pass'],
        'grader_did_not_change_odt': original_hash == sha256(workspace / 'report.odt')}
    roles = {role: {'checks': values, 'score': sum(values.values()) / len(values), 'success': all(values.values())}
        for role, values in checks.items()}
    upstream = [role for role in 'abc' if not roles[role]['success']]
    roles['d']['unmet_upstream_roles'] = upstream
    roles['d']['dependency_status'] = 'upstream_incomplete' if upstream else 'ready'
    report = {'roles': roles, 'joint': joint, 'success': all(joint.values()) and all(row['success'] for row in roles.values()),
        'toc_evidence': toc_details, 'pdf_comparison': comparison, 'saved_odt_sha256': original_hash,
        'scope': 'WeaveBench-seeded derived workload; not an official score',
        'limitations': ['Audit explanation checked for nonemptiness, not honesty; use trajectories for authenticity.',
            'Ownership and readiness protocol compliance require trajectory review, not artifact-only grading.']}
    write_json(output / 'grade.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'baseline', 'live', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = grade(args.workspace, json.loads(args.baseline.read_text()), json.loads(args.live.read_text()), args.out)
    print(json.dumps(result, ensure_ascii=False))
