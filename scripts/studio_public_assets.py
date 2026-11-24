"""Reviewed, bounded file inventory shared by the Studio build and release gate."""

from pathlib import Path
import stat

# Bounded Studio asset budget, including local Office text extraction and
# bilingual decision support in the standalone HTML.
# The reviewed chat workflow checklist adds ~5.8 KiB to the bundled
# self-contained shell. Keep a hard asset ceiling and fail closed above it.
# Reviewed chat-model status UI increases the complete static shell by ~4.3 KiB.
# Keep a strict 620 KiB-class per-file cap (not an unbounded exception).
# Reviewed per-answer model routing receipts add ~2.4 KiB to the public
# Studio HTML. Credential preflight adds a small additional prompt-review panel;
# increase only the HTML ceiling by another 5 KiB. Retain the
# original cap on every other static asset and the independent PDF worker cap.
# The bilingual chat-to-tool boundary disclosures add ~3 KiB to the bundled shell.
# A scoped, transient, review-only outcome report adds ~4 KiB; public HTML cap stays at 650 KiB-class.
MAX_FILE = 625_000
STUDIO_INDEX_LIMIT = 650_000
PDF_MODULES = ("pdf/studio-pdf.mjs", "pdf/pdf.min.mjs", "pdf/pdf.worker.min.mjs")
PDF_FILES = PDF_MODULES + ("pdf/LICENSE-pdfjs.txt",)
WORKER_LIMIT = 1_300_000
LEGACY_FILES = (
    "index.html",
    "service-worker.js",
    "manifest.json",
    "icons/nexus-192.png",
    "icons/nexus-512.png",
    "device/device-engine.js",
    "device/device-ui.js",
    "device/device-worker.js",
    "device/model-manifest.json",
    "device/vendor/LICENSE-jinja.txt",
    "device/vendor/LICENSE-onnxruntime.txt",
    "device/vendor/LICENSE-transformers.txt",
    "device/vendor/ort-wasm-simd-threaded.asyncify.mjs",
)
ASTRONOMY_MODULE = "vendor/astronomy-2.1.19.min.js"
HISTORICAL_LIVE_FILES = LEGACY_FILES + PDF_FILES
FILES = HISTORICAL_LIVE_FILES + (ASTRONOMY_MODULE,)

def asset_limit(name):
    if name == 'pdf/pdf.worker.min.mjs':
        return WORKER_LIMIT
    if name == 'index.html':
        return STUDIO_INDEX_LIMIT
    return MAX_FILE


def check_public_tree(root):
    return _check_tree(root, FILES)


def check_historical_live_tree(root):
    # Only for the immutable 17-file prior-live fallback and restore protocol.
    return _check_tree(root, HISTORICAL_LIVE_FILES)


def _check_tree(root, inventory):
    root = Path(root)
    paths = {}
    if root.is_symlink() or not root.is_dir():
        raise ValueError("public Studio directory must be a regular directory")
    for path in root.rglob("*"):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        relative = path.relative_to(root).as_posix()
        if (relative not in inventory or not stat.S_ISREG(info.st_mode) or
                info.st_nlink != 1 or not 0 < info.st_size <= asset_limit(relative)):
            raise ValueError("public Studio contains an unreviewed or unsupported asset")
        paths[relative] = path
    if paths.keys() != set(inventory):
        raise ValueError("public Studio assets are incomplete")
    return paths
