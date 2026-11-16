"""Read-only UNO observation; this file contains no reference answers or grading."""
import argparse
import json
import time


def connect(port=2002, timeout=30):
    import uno
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
    deadline = time.monotonic() + timeout
    while True:
        try:
            context = resolver.resolve(f'uno:socket,host=127.0.0.1,port={port};urp;StarOffice.ComponentContext')
            return context, context.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', context)
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.25)


def value(item):
    if item is None or isinstance(item, (bool, str, int, float)):
        return item
    if isinstance(item, (tuple, list)):
        return [value(element) for element in item]
    if hasattr(item, 'value'):
        return item.value
    return str(item)


def properties(item, names):
    result = {}
    for name in names:
        try:
            result[name] = value(item.getPropertyValue(name))
        except Exception:
            result[name] = None
    return result


def paragraph_range(document, anchor):
    cursor = document.Text.createTextCursorByRange(anchor.Start)
    cursor.gotoStartOfParagraph(False)
    cursor.gotoEndOfParagraph(True)
    return cursor


TEXT_PROPERTIES = ('CharFontName', 'CharHeight', 'CharWeight', 'CharColor')
PARAGRAPH_PROPERTIES = ('ParaStyleName', 'OutlineLevel', 'ParaKeepTogether', 'BreakType',
    'PageStyleName', 'NumberingStyleName', 'NumberingLevel', 'ListLabelString') + TEXT_PROPERTIES


def snapshot(document):
    modified_before = document.isModified()
    paragraphs = []
    enumeration = document.Text.createEnumeration()
    while enumeration.hasMoreElements():
        paragraph = enumeration.nextElement()
        if paragraph.supportsService('com.sun.star.text.Paragraph'):
            cursor = paragraph_range(document, paragraph)
            paragraphs.append({'text': cursor.String, **properties(cursor, PARAGRAPH_PROPERTIES)})
    sections = []
    bookmarks = document.Bookmarks
    for name in bookmarks.ElementNames:
        if not name.startswith('sec_'):
            continue
        anchor = bookmarks.getByName(name).Anchor
        cursor = paragraph_range(document, anchor)
        sections.append({'id': name, 'bookmark_text': anchor.String, 'text': cursor.String,
            **properties(cursor, PARAGRAPH_PROPERTIES)})
    styles = document.StyleFamilies.getByName('ParagraphStyles')
    paragraph_styles = {name: properties(styles.getByName(name), TEXT_PROPERTIES + ('ParaKeepTogether', 'OutlineLevel'))
        for name in ('Heading 1', 'Text body') if styles.hasByName(name)}
    used = sorted({row['PageStyleName'] for row in paragraphs if row['PageStyleName']})
    page_styles = {}
    for name in used:
        style = document.StyleFamilies.getByName('PageStyles').getByName(name)
        row = properties(style, ('Width', 'Height', 'LeftMargin', 'RightMargin', 'TopMargin',
            'BottomMargin', 'IsLandscape', 'FooterIsOn', 'FooterIsShared', 'FirstIsShared'))
        row['footer_fields'] = []
        for footer_name in ('FooterText', 'FooterTextLeft', 'FooterTextFirst'):
            try:
                footer = style.getPropertyValue(footer_name)
                enumeration = footer.createEnumeration()
                while enumeration.hasMoreElements():
                    paragraph = enumeration.nextElement()
                    if not paragraph.supportsService('com.sun.star.text.Paragraph'):
                        continue
                    portions = paragraph.createEnumeration()
                    while portions.hasMoreElements():
                        portion = portions.nextElement()
                        if portion.TextPortionType == 'TextField':
                            field = portion.TextField
                            row['footer_fields'].append({'area': footer_name,
                                'services': list(field.SupportedServiceNames),
                                **properties(field, ('SubType', 'Offset', 'NumberingType'))})
            except Exception:
                continue
        page_styles[name] = row
    numbering = [{item.Name: value(item.Value) for item in document.ChapterNumberingRules.getByIndex(index)}
        for index in range(document.ChapterNumberingRules.Count)]
    indexes = []
    for index in range(document.DocumentIndexes.Count):
        table = document.DocumentIndexes.getByIndex(index)
        indexes.append({'services': list(table.SupportedServiceNames), 'text': table.Anchor.String,
            **properties(table, ('Title', 'CreateFromOutline', 'Level', 'CreateFromMarks'))})
    return {'url': document.URL, 'modified': modified_before, 'modified_after': document.isModified(),
        'paragraphs': paragraphs, 'sections': sorted(sections, key=lambda row: row['id']), 'paragraph_styles': paragraph_styles,
        'page_styles': page_styles, 'numbering': numbering, 'indexes': indexes}


def live_snapshot(port=2002, path='/workspace/report.odt'):
    import uno
    _, desktop = connect(port)
    documents = []
    enumeration = desktop.Components.createEnumeration()
    while enumeration.hasMoreElements():
        document = enumeration.nextElement()
        if document.supportsService('com.sun.star.text.TextDocument'):
            documents.append(document)
    url = uno.systemPathToFileUrl(path)
    matching = [document for document in documents if document.URL == url]
    if len(matching) != 1:
        raise RuntimeError(f'Expected one canonical Writer document, found {len(matching)}')
    return {'captured_at': time.time(), 'writer_document_count': len(documents), **snapshot(matching[0])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=2002)
    parser.add_argument('--path', default='/workspace/report.odt')
    args = parser.parse_args()
    print(json.dumps(live_snapshot(args.port, args.path), ensure_ascii=False))
