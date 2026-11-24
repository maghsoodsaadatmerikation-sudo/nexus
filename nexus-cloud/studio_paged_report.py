"""Deterministic paginated PDF and editable presentation analysis reports."""
from __future__ import annotations

from xml.sax.saxutils import escape
from textwrap import wrap
from studio_office_report import NOTICE, REL, package, relationships, content_types

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"


def chunks(rows, size):
    return [rows[i:i + size] for i in range(0, len(rows), size)] or [[]]


def row_text(row):
    step, operation, kind, metric, value, source_step, source_metric = row
    label = metric if kind == "metric" else f"input {source_step}.{source_metric}"
    return f"{step} | {operation} | {label} | {value}"


def pdf(digest, rows):
    """ASCII-only report fields, standard Helvetica, explicit cross-reference table."""
    lines = [line for row in rows for line in wrap(row_text(row), width=100)]
    pages = chunks(lines, 24)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # Pages tree filled after allocating page objects.
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    def text(x, y, size, value):
        value = str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return f"BT /F1 {size} Tf 1 0 0 1 {x} {y} Tm ({value}) Tj ET\n"

    kids = []
    for index, group in enumerate(pages, 1):
        page_id = len(objects) + 1
        stream_id = page_id + 1
        kids.append(f"{page_id} 0 R")
        content = "0.10 0.15 0.22 rg\n" + text(36, 565, 20, "NEXUS analysis report")
        content += text(36, 541, 10, NOTICE)
        content += text(36, 524, 10, "Review SHA-256: " + digest)
        content += text(36, 502, 10, "Step | Operation | Metric / input source | Value")
        content += "0.2 0.4 0.5 RG 36 494 m 806 494 l S\n"
        for line, row in enumerate(group):
            content += text(36, 477 - line * 17, 10, row)
        content += text(36, 32, 9, f"Page {index} of {len(pages)}")
        encoded = content.encode("ascii")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>".encode("ascii")
        )
        objects.append(f"<< /Length {len(encoded)} >>\nstream\n".encode("ascii")
                       + encoded + b"endstream")
    objects[1] = f"<< /Type /Pages /Count {len(kids)} /Kids [{' '.join(kids)}] >>".encode("ascii")
    data = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(data)


def pptx(digest, rows):
    """Editable native slide shapes; fixed layout and no external resources."""
    pages = chunks(rows, 9)
    ns = f'xmlns:a="{A}" xmlns:r="{REL}" xmlns:p="{P}"'
    group_root = (
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
    )

    def shape(index, text, x, y, width, height, size, color):
        return (
            f'<p:sp><p:nvSpPr><p:cNvPr id="{index}" name="Text {index}"/>'
            '<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/>'
            '<a:ln><a:noFill/></a:ln></p:spPr><p:txBody>'
            '<a:bodyPr wrap="square" lIns="0" rIns="0" tIns="0" bIns="0"/>'
            '<a:lstStyle/><a:p><a:r>'
            f'<a:rPr lang="en-US" sz="{size}"><a:solidFill><a:srgbClr val="{color}"/>'
            '</a:solidFill>'
            '<a:latin typeface="Arial"/></a:rPr>'
            f'<a:t>{escape(text)}</a:t></a:r></a:p></p:txBody></p:sp>'
        )

    def common(shapes=""):
        return f'<p:cSld><p:spTree>{group_root}{shapes}</p:spTree></p:cSld>'

    color_map = ('<p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" '
                 'accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" '
                 'folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>')
    color_override = '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>'
    master = (f'<p:sldMaster {ns}>{common()}{color_map}'
              '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/>'
              '</p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/>'
              '</p:txStyles></p:sldMaster>')
    layout = (f'<p:sldLayout {ns} type="blank" preserve="1">{common()}{color_override}</p:sldLayout>')
    colors = {"dk1":"172538", "lt1":"FFFFFF", "dk2":"334155", "lt2":"F1F5F9",
              "accent1":"16856C", "accent2":"6366A1", "accent3":"2563EB",
              "accent4":"A16207", "accent5":"475569", "accent6":"64748B",
              "hlink":"2563EB", "folHlink":"6366A1"}
    scheme = "".join(f'<a:{k}><a:srgbClr val="{v}"/></a:{k}>' for k,v in colors.items())
    font = '<a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/>'
    fill = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    line_style = '<a:ln w="9525">' + fill + '</a:ln>'
    theme = (f'<a:theme xmlns:a="{A}" name="NEXUS"><a:themeElements>'
             f'<a:clrScheme name="NEXUS">{scheme}</a:clrScheme>'
             f'<a:fontScheme name="Arial"><a:majorFont>{font}</a:majorFont>'
             f'<a:minorFont>{font}</a:minorFont></a:fontScheme>'
             f'<a:fmtScheme name="NEXUS"><a:fillStyleLst>{fill * 3}</a:fillStyleLst>'
             f'<a:lnStyleLst>{line_style * 3}</a:lnStyleLst>'
             '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle>'
             '<a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/>'
             f'</a:effectStyle></a:effectStyleLst><a:bgFillStyleLst>{fill * 3}</a:bgFillStyleLst>'
             '</a:fmtScheme></a:themeElements></a:theme>')
    prefix = "application/vnd.openxmlformats-officedocument."
    overrides = [
        ("ppt/presentation.xml", prefix + "presentationml.presentation.main+xml"),
        ("ppt/slideMasters/slideMaster1.xml", prefix + "presentationml.slideMaster+xml"),
        ("ppt/slideLayouts/slideLayout1.xml", prefix + "presentationml.slideLayout+xml"),
        ("ppt/theme/theme1.xml", prefix + "theme+xml"),
    ]
    parts = {
        "_rels/.rels": relationships([("rId1", "officeDocument", "ppt/presentation.xml")]),
        "ppt/slideMasters/slideMaster1.xml": master,
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": relationships([
            ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"),
            ("rId2", "theme", "../theme/theme1.xml")]),
        "ppt/slideLayouts/slideLayout1.xml": layout,
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": relationships([
            ("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")]),
        "ppt/theme/theme1.xml": theme,
    }
    slide_ids = []
    pres_rel = [("rId1", "slideMaster", "slideMasters/slideMaster1.xml")]
    for index, group in enumerate(pages, 1):
        width = 11200000
        shapes = shape(2, "NEXUS | Analysis report", 500000, 260000, width, 500000, 3000, "172538")
        shapes += shape(3, NOTICE, 500000, 850000, width, 350000, 1400, "475569")
        shapes += shape(4, "Review SHA-256: " + digest, 500000, 1250000, width, 320000, 1200, "475569")
        for j, row in enumerate(group):
            shapes += shape(j + 5, row_text(row), 500000, 1750000 + j * 475000,
                            width, 450000, 1300, "172538")
        shapes += shape(20, f"{index} / {len(pages)}", 500000, 6450000, width, 240000, 1100, "16856C")
        name = f"ppt/slides/slide{index}.xml"
        parts[name] = f'<p:sld {ns}>{common(shapes)}{color_override}</p:sld>'
        parts[f"ppt/slides/_rels/slide{index}.xml.rels"] = relationships([
            ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml")])
        overrides.append((name, prefix + "presentationml.slide+xml"))
        rid = f"rId{index + 1}"
        slide_ids.append(f'<p:sldId id="{255 + index}" r:id="{rid}"/>')
        pres_rel.append((rid, "slide", f"slides/slide{index}.xml"))
    parts["ppt/presentation.xml"] = (
        f'<p:presentation {ns}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
        f'</p:sldMasterIdLst><p:sldIdLst>{"".join(slide_ids)}</p:sldIdLst>'
        '<p:sldSz cx="12192000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/>'
        '</p:presentation>'
    )
    parts["ppt/_rels/presentation.xml.rels"] = relationships(pres_rel)
    parts["[Content_Types].xml"] = content_types(overrides)
    return package(parts)
