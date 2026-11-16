"""Public specification and byte-traceable preparation of a Writer seed variant."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from zipfile import ZipFile


PAIR = 'wvwriterconf'
SEED_ID = 'DOC_task_2_heading_style_normalize'
SEED_COMMIT = 'ec498fc530b685d2fea5823a64a0f7538c8bbf6a'
TITLES = ['Background', 'Methodology', 'Results', 'Discussion', 'Conclusion', 'Appendix A: Data',
    'Appendix B: Code', 'Limitations', 'Future Work', 'Acknowledgments', 'Funding', 'References',
    'Glossary', 'Index', 'Author Bios']
RENAMES = {'sec_03': 'Findings', 'sec_04': 'Interpretation', 'sec_15': 'Contributors'}
NOTE = ('Review note: The findings describe the supplied sample rather than a representative population. '
    'The sample is small, its selection was not randomized, and the observations do not establish causal effects. '
    'Some inputs were collected at different times, so apparent differences may reflect changing conditions '
    'rather than a stable property of the process under review. Quantitative summaries should therefore be '
    'read alongside the underlying records and the stated assumptions. Missing observations have not been '
    'silently replaced with zero, and uncertain measurements should not be reported with unsupported precision. '
    'The revised terminology improves consistency but does not add evidence to the study. Formatting and '
    'pagination serve readability; they do not change the scope of the conclusions. Readers should distinguish '
    'a documented observation from an inference, and an inference from a recommendation. Before relying on '
    'the report in another setting, an independent reviewer should examine the source material, the inclusion '
    'criteria, and the relevance of the sample to that setting. Additional observations collected under a '
    'consistent protocol would be needed to assess reproducibility and to quantify uncertainty. These '
    'limitations remain applicable even when the final report is complete and internally consistent.')
NS = {'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
    'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
    'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
    'fo': 'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0'}


def tag(prefix, name):
    return '{' + NS[prefix] + '}' + name


def section_rows():
    return [{'id': f'sec_{index+1:02d}', 'original_title': title,
        'final_title': RENAMES.get(f'sec_{index+1:02d}', title), 'number': index+1}
        for index, title in enumerate(TITLES)]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def build(seed, output):
    seed, output = Path(seed), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    inputs = output / 'dataset/pairs' / PAIR / 'inputs'
    inputs.mkdir(parents=True)
    private = output / 'private'
    private.mkdir()
    source = seed / 'tasks/workspace/DOC/task_2_heading_style_normalize/exec/report.odt'
    original_spec = seed / 'tasks/DOC' / (SEED_ID + '.md')
    baseline = {'sections': [], 'original_wrong_ids': []}
    with ZipFile(source) as archive:
        content = archive.read('content.xml')
        for _, namespace in ET.iterparse(io.BytesIO(content), events=['start-ns']):
            prefix, uri = namespace
            if prefix != 'xml':
                ET.register_namespace(prefix, uri)
        tree = ET.fromstring(content)
        body = tree.find('office:body/office:text', NS)
        original_nodes = list(body)
        assert len(original_nodes) == 45
        for index, row in enumerate(section_rows()):
            heading = original_nodes[index * 3]
            assert ''.join(heading.itertext()) == row['original_title']
            good = heading.tag == tag('text', 'h') and heading.get(tag('text', 'outline-level')) == '1'
            if not good:
                baseline['original_wrong_ids'].append(row['id'])
            baseline['sections'].append(dict(row, body=[''.join(node.itertext()) for node in original_nodes[index*3+1:index*3+3]]))
            start = ET.Element(tag('text', 'bookmark-start'), {tag('text', 'name'): row['id']})
            start.tail = heading.text
            heading.text = None
            heading.insert(0, start)
            heading.append(ET.Element(tag('text', 'bookmark-end'), {tag('text', 'name'): row['id']}))
        assert len(baseline['original_wrong_ids']) == 7
        with ZipFile(inputs / 'report.odt', 'w') as destination:
            for entry in archive.infolist():
                destination.writestr(entry, ET.tostring(tree, encoding='utf-8', xml_declaration=True)
                    if entry.filename == 'content.xml' else archive.read(entry.filename))
    for folder in ('results', 'handoff'):
        (inputs / folder).mkdir()
    source_dir = Path(__file__).parent
    for role in 'abcd':
        shutil.copy2(source_dir / ('task_' + role + '.md'), inputs.parent / ('task_' + role + '.md'))
    for name in ('PROJECT_BRIEF.md', 'ACCEPTANCE.md'):
        shutil.copy2(source_dir / name, inputs / name)
    (inputs / 'review_note.txt').write_text(NOTE + '\n')
    write_json(inputs / 'contract.json', {'version': 1, 'seed': SEED_ID, 'sections': section_rows(),
        'canonical_document': '/workspace/report.odt', 'body_note_section': 'sec_08',
        'heading_style': {'font': 'Liberation Sans', 'points': 18, 'bold': True, 'color': '#1F3A5F'},
        'body_style': {'font': 'Liberation Sans', 'points': 11},
        'page': {'width_mm': 210, 'height_mm': 297, 'margins_mm': 20},
        'numbering': {'start': 1, 'format': 'Arabic', 'suffix': '. '},
        'publisher_outputs': ['results/report.pdf', 'results/publication.json'],
        'handoff_is_untrusted': True, 'reference_solutions_exposed': False})
    write_json(private / 'baseline.json', baseline)
    shutil.copy2(source, private / 'original-report.odt')
    shutil.copy2(original_spec, private / 'original-task.md')
    write_json(output / 'provenance.json', {'seed_id': SEED_ID, 'dataset_commit': SEED_COMMIT,
        'original_odt_sha256': digest(source), 'prepared_odt_sha256': digest(inputs / 'report.odt'),
        'original_task_sha256': digest(original_spec), 'label': 'WeaveBench-seeded derived workload, not an official task/score',
        'fixture_changes': ['Added 15 stable bookmark ranges around the existing section titles; visible text and initial heading errors unchanged'],
        'task_extensions': ['Shared canonical document', 'Three title revisions', 'Native chapter numbering',
            'Shared typography/page style', 'Supplied limitations note', 'Version-bound TOC/PDF publication'],
        'input_hashes': {str(path.relative_to(inputs)): digest(path) for path in sorted(inputs.rglob('*')) if path.is_file()}})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.seed, args.out)
