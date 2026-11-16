"""Private native feasibility operations, never mounted into a model desktop."""
import argparse
import hashlib
import json
from pathlib import Path

from tasks.weavebench_writer_conflict.observer import connect, paragraph_range, snapshot
from tasks.weavebench_writer_conflict.spec import NOTE, RENAMES


def prop(name, item):
    import uno
    result = uno.createUnoStruct('com.sun.star.beans.PropertyValue')
    result.Name, result.Value = name, item
    return result


def constant(name):
    import uno
    return uno.getConstantByName(name)


def get_document():
    _, desktop = connect()
    components = desktop.Components.createEnumeration()
    while components.hasMoreElements():
        document = components.nextElement()
        if document.supportsService('com.sun.star.text.TextDocument') and document.URL.endswith('/report.odt'):
            return document
    raise RuntimeError('No canonical document')


def rename(document, identifier, title):
    bookmark = document.Bookmarks.getByName(identifier)
    cursor = paragraph_range(document, bookmark.Anchor)
    bookmark.dispose()
    cursor.String = title
    replacement = document.createInstance('com.sun.star.text.Bookmark')
    replacement.Name = identifier
    document.Text.insertTextContent(cursor, replacement, True)


def apply_role(document, role, workspace):
    import uno
    workspace = Path(workspace)
    if role == 'a':
        state = snapshot(document)
        wrong = sorted(row['id'] for row in state['sections']
            if row['ParaStyleName'] != 'Heading 1' or row['OutlineLevel'] != 1)
        (workspace / 'results/structure_audit.json').write_text(json.dumps({
            'wrong_section_ids': wrong, 'inspection': 'Inspected UNO ParaStyleName and OutlineLevel at every bookmark before repair.'}))
        for row in state['sections']:
            cursor = paragraph_range(document, document.Bookmarks.getByName(row['id']).Anchor)
            cursor.ParaStyleName = 'Heading 1'
            cursor.OutlineLevel = 1
    elif role == 'b':
        for identifier, title in RENAMES.items():
            rename(document, identifier, title)
        rules = document.ChapterNumberingRules
        updates = {'HeadingStyleName': 'Heading 1', 'NumberingType': constant('com.sun.star.style.NumberingType.ARABIC'),
            'Prefix': '', 'Suffix': '. ', 'StartWith': 1}
        uno.invoke(rules, 'replaceByIndex', (0, uno.Any('[]com.sun.star.beans.PropertyValue',
            tuple(prop(name, item) for name, item in updates.items()))))
    elif role == 'c':
        styles = document.StyleFamilies.getByName('ParagraphStyles')
        heading = styles.getByName('Heading 1')
        heading.CharFontName, heading.CharHeight = 'Liberation Sans', 18
        heading.CharWeight = constant('com.sun.star.awt.FontWeight.BOLD')
        heading.CharColor, heading.ParaKeepTogether = 0x1F3A5F, True
        body = styles.getByName('Text body')
        body.CharFontName, body.CharHeight = 'Liberation Sans', 11
        anchors = [document.Bookmarks.getByName(f'sec_{index:02d}').Anchor.Start for index in range(1, 16)]
        enumeration = document.Text.createEnumeration()
        while enumeration.hasMoreElements():
            paragraph = enumeration.nextElement()
            if not paragraph.supportsService('com.sun.star.text.Paragraph'):
                continue
            if any(document.Text.compareRegionStarts(paragraph.Start, anchor) == 0 for anchor in anchors):
                continue
            cursor = paragraph_range(document, paragraph)
            if cursor.ParaStyleName.startswith('Contents'):
                continue
            cursor.ParaStyleName = 'Text body'
            for name in ('CharFontName', 'CharHeight'):
                cursor.setPropertyToDefault(name)
        cursor = document.Text.createTextCursorByRange(document.Bookmarks.getByName('sec_09').Anchor.Start)
        cursor.gotoPreviousParagraph(False)
        cursor.gotoStartOfParagraph(False)
        cursor.gotoEndOfParagraph(True)
        if cursor.String:
            raise RuntimeError('Expected the original empty paragraph before sec_09')
        cursor.String = NOTE
        cursor.ParaStyleName = 'Text body'
        for name in ('CharFontName', 'CharHeight'):
            cursor.setPropertyToDefault(name)
        page_name = document.Text.createTextCursor().PageStyleName
        page = document.StyleFamilies.getByName('PageStyles').getByName(page_name)
        page.Width, page.Height, page.IsLandscape = 21000, 29700, False
        page.LeftMargin = page.RightMargin = page.TopMargin = page.BottomMargin = 2000
        page.FooterIsOn = True
        footer = page.FooterText
        footer.String = ''
        field = document.createInstance('com.sun.star.text.textfield.PageNumber')
        field.SubType = uno.Enum('com.sun.star.text.PageNumberType', 'CURRENT')
        field.NumberingType = constant('com.sun.star.style.NumberingType.ARABIC')
        footer.insertTextContent(footer.createTextCursor(), field, False)
    elif role == 'd':
        if document.DocumentIndexes.Count:
            table = document.DocumentIndexes.getByIndex(0)
        else:
            cursor = document.Text.createTextCursor()
            cursor.gotoStart(False)
            document.Text.insertControlCharacter(cursor, constant('com.sun.star.text.ControlCharacter.PARAGRAPH_BREAK'), False)
            cursor.gotoStart(False)
            cursor.ParaStyleName = 'Text body'
            cursor.OutlineLevel = 0
            table = document.createInstance('com.sun.star.text.ContentIndex')
            table.Title, table.CreateFromOutline, table.CreateFromMarks, table.Level = 'Contents', True, False, 1
            document.Text.insertTextContent(cursor, table, False)
        first = paragraph_range(document, document.Bookmarks.getByName('sec_01').Anchor)
        first.BreakType = uno.Enum('com.sun.star.style.BreakType', 'PAGE_BEFORE')
        document.TextFields.refresh()
        table.update()
        document.refresh()
        table.update()
    else:
        raise ValueError(role)
    document.store()
    if role == 'd':
        document.storeToURL(uno.systemPathToFileUrl(str(workspace / 'results/report.pdf')),
            (prop('FilterName', 'writer_pdf_Export'), prop('Overwrite', True)))
        receipt(workspace)
    (workspace / 'handoff' / (role + '.json')).write_text(json.dumps({'role': role, 'ready': True, 'note': 'Native reference committed'}))


def receipt(workspace):
    workspace = Path(workspace)
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    (workspace / 'results/publication.json').write_text(json.dumps({
        'odt_sha256': digest(workspace / 'report.odt'), 'pdf_sha256': digest(workspace / 'results/report.pdf'),
        'section_ids': [f'sec_{index:02d}' for index in range(1, 16)]}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', choices=list('abcd'), required=True)
    parser.add_argument('--workspace', type=Path, default=Path('/workspace'))
    args = parser.parse_args()
    apply_role(get_document(), args.role, args.workspace)
