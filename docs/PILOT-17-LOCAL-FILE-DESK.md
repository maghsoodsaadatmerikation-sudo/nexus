# Pilot 17 — local file input and real document exports

The Files panel accepts any browser-selected file type as an immutable,
SHA-256-identified snapshot in this open tab: at most 20 files, 10 MiB each,
20 MiB total. It does **not** upload files to an application server. A selected
file's MIME/name are metadata, not evidence of authenticity or safety. Original
bytes can be downloaded or retained in a separately confirmed ZIP bundle.
Filenames are made portable/safe for download; original names remain in the
bundle manifest. Originals download as generic binary data, never an inline
active-content preview. Nothing automatically opens a file in another app.

## What is and is not read

UTF-8/BOM UTF-16 text and source files can be previewed in a readonly textarea.
HTML/SVG/code remain inert text. Native raw-DEFLATE support permits bounded
DOCX main-body paragraphs, XLSX shared/inline cell strings and literal formulas,
and PPTX slide text. These are plain text extraction, not layout rendering,
OCR, audio transcription, media understanding or document authenticity checks.
Other files, including PDFs/images/audio/video/legacy Office, stay as original
byte snapshots with metadata and download access. Unsupported/corrupt previews
leave the original intact.

Office ZIP reading rejects unsafe/duplicate names, encryption, malformed offsets,
CRC/size differences, XML DTD/entities and over-budget XML/inflation. Limits:
500 archive entries, 1 MiB per extracted XML part, 3 MiB total extracted XML,
20 sheets/slides, 2000 spreadsheet rows, 5000 cells, 10000 shared strings and
100000 preview characters. No external relationship, macro, formula, script or
embedded object executes. These limits are not a malware/safety scan.

## Human evidence boundary

Select an excerpt of at most 2000 characters and choose Use selected text as a
claim draft. Existing claim/source drafts require replacement confirmation.
The result is unregistered external evidence with unknown uncertainty and a
local-file SHA-256 source reference. The user must still Register a question
and Add claim explicitly. Reading a file never records a human judgment.

The tray and pending admission participate in draft/replacement protection.
New/import/local restore cannot silently discard the first files. An actual
workspace replacement clears the tray; late read/preview/export work cannot
attach to the new workspace. Changing interface language preserves files.
File additions/removals, data or language changes cancel stale bundle output.

## Output formats

- TXT: readable committed report, UTF-8.
- Markdown: escaped committed report; user HTML/image syntax remains inert.
- CSV: quoted evidence/workspace table with a UTF-8 BOM and text prefixes for
  formula-looking cells. Use JSON to retain exact raw strings.
- HTML: standalone escaped report with a restrictive CSP, no active resources.
- DOCX: a real Open Packaging Convention ZIP with WordprocessingML paragraphs.
- XLSX: a real workbook/worksheet package; every cell is inline text, no formulas.
- XML: escaped structured report. XML-invalid controls become visible escapes.
- ZIP: unencrypted workspace.json, report.txt, manifest.json and all current
  original byte snapshots. Manifest paths are safe, unique and SHA-256 verified.
- PDF: the existing committed-report browser print/save dialog. This does not
  manufacture a renamed text file or prove that a PDF was saved on a device.

Every plaintext download requires confirmation; original downloads have their
own confirmation. Files/previews/drafts/passwords are excluded from generated
reports until explicitly registered. The ZIP alone carries current originals.
Encrypted workspace JSON/local checkpoints do not include the tray. Exporting
an encrypted workspace is therefore not an attachment backup. Closing the tab,
forced mobile termination or browser memory loss may discard unsaved originals.
No new plaintext browser store, network service, account or provider cost.

## Verification

The dedicated real-Chromium file witness covers 33 behaviors per viewport:
any-type binary admission, first-tray cancellation, inert markup, preview/excerpt
boundaries, genuine compressed Office text, hostile/over-budget ZIP/XML rejection,
limits, original-byte download, all formats, PDF-dialog entry, unchanged audit,
reopened generated Word, export/admission races and late read cancellation.
Independent Python zipfile/ElementTree/csv/hashlib readers validate generated ZIP
CRCs, Word/Excel XML and relationship targets, text-only Excel cells, CSV formula
escaping, Unicode text and every bundled original's SHA-256. Only synthetic
fixtures are used; output bytes are removed from sanitized reports.

Existing voice/language/workshop/report/draft/Rust/offline witnesses remain
separate. Public source/adapter acceptance and actual offline reopening follow
manual deployment of the same existing static service. No original Railway
volume operation, production recovery or new release Seal is claimed.

References:
- https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document
- https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/structure-of-a-spreadsheetml-document
- https://developer.mozilla.org/en-US/docs/Web/API/DecompressionStream/DecompressionStream
