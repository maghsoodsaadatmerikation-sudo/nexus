"""Minimal deterministic Office packages for bounded, trusted report rows."""
from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
NOTICE = "Computational consistency only; not independent source verification or human approval."


def package(parts):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, content in sorted(parts.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (XML + content).encode("utf-8"))
    return stream.getvalue()


def relationships(items):
    return (f'<Relationships xmlns="{PKG}">' + "".join(
        f'<Relationship Id="{key}" Type="{REL}/{kind}" Target="{target}"/>'
        for key, kind, target in items
    ) + "</Relationships>")


def content_types(overrides):
    return (f'<Types xmlns="{CT}">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            + "".join(f'<Override PartName="/{name}" ContentType="{kind}"/>'
                      for name, kind in overrides) + "</Types>")


def xlsx(digest, columns, rows):
    # Fixed nine-column maximum; numbers remain numeric, text uses inline
    # strings. No formulas, hyperlinks, macros, or external relationships.
    def sheet(table):
        output = []
        for index, row in enumerate(table, 1):
            cells = []
            for col, value in enumerate(row):
                address = f"{chr(65 + col)}{index}"
                if type(value) in (int, float):
                    cells.append(f'<c r="{address}"><v>{value}</v></c>')
                else:
                    cells.append(f'<c r="{address}" t="inlineStr"><is><t>'
                                 f'{escape(str(value))}</t></is></c>')
            output.append(f'<row r="{index}">{"".join(cells)}</row>')
        return (f'<worksheet xmlns="{S}"><sheetData>{"".join(output)}'
                '</sheetData></worksheet>')

    workbook = (f'<workbook xmlns="{S}" xmlns:r="{REL}"><sheets>'
                '<sheet name="Report" sheetId="1" r:id="rId1"/>'
                '<sheet name="Metadata" sheetId="2" r:id="rId2"/></sheets></workbook>')
    prefix = "application/vnd.openxmlformats-officedocument.spreadsheetml."
    return package({
        "[Content_Types].xml": content_types([
            ("xl/workbook.xml", prefix + "sheet.main+xml"),
            ("xl/worksheets/sheet1.xml", prefix + "worksheet+xml"),
            ("xl/worksheets/sheet2.xml", prefix + "worksheet+xml"),
        ]),
        "_rels/.rels": relationships([("rId1", "officeDocument", "xl/workbook.xml")]),
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": relationships([
            ("rId1", "worksheet", "worksheets/sheet1.xml"),
            ("rId2", "worksheet", "worksheets/sheet2.xml"),
        ]),
        "xl/worksheets/sheet1.xml": sheet([columns, *rows]),
        "xl/worksheets/sheet2.xml": sheet([
            ("field", "value"), ("review_sha256", digest),
            ("consistency", "consistent"), ("notice", NOTICE),
        ]),
    })


def docx(digest, columns, rows):
    def paragraph(value, bold=False, size=20):
        props = ("<w:b/>" if bold else "") + f'<w:sz w:val="{size}"/>'
        return (f'<w:p><w:r><w:rPr>{props}</w:rPr>'
                f'<w:t xml:space="preserve">{escape(str(value))}</w:t></w:r></w:p>')

    widths = (1500, 2400, 900, 1800, 1500, 1500, 1800)
    def table_row(row, header=False):
        cells = "".join(
            f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>'
            f'{paragraph(value, bold=header, size=18)}</w:tc>'
            for width, value in zip(widths, row)
        )
        return ("<w:tr>" + ("<w:trPr><w:tblHeader/></w:trPr>" if header else "")
                + cells + "</w:tr>")

    grid = "".join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    table = ('<w:tbl><w:tblPr><w:tblW w:w="11400" w:type="dxa"/>'
             '<w:tblBorders><w:top w:val="single" w:sz="4"/>'
             '<w:left w:val="single" w:sz="4"/><w:bottom w:val="single" w:sz="4"/>'
             '<w:right w:val="single" w:sz="4"/><w:insideH w:val="single" w:sz="4"/>'
             '<w:insideV w:val="single" w:sz="4"/></w:tblBorders></w:tblPr>'
             f'<w:tblGrid>{grid}</w:tblGrid>'
             + table_row(columns, True) + "".join(table_row(row) for row in rows)
             + "</w:tbl>")
    document = (f'<w:document xmlns:w="{W}"><w:body>'
                + paragraph("NEXUS analysis report", True, 32)
                + paragraph(NOTICE) + paragraph("Review SHA-256: " + digest)
                + table + '<w:sectPr><w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>'
                '<w:pgMar w:top="900" w:right="900" w:bottom="900" w:left="900" '
                'w:header="450" w:footer="450" w:gutter="0"/>'
                '</w:sectPr></w:body></w:document>')
    return package({
        "[Content_Types].xml": content_types([
            ("word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")
        ]),
        "_rels/.rels": relationships([("rId1", "officeDocument", "word/document.xml")]),
        "word/document.xml": document,
    })
