"""Reviewed, bounded file inventory shared by the Studio build and release gate."""

from pathlib import Path
import stat

# Bounded standalone HTML budget, including the calendar reminder panel.
MAX_FILE = 530_000
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
FILES = LEGACY_FILES + PDF_FILES

def asset_limit(name):
    return WORKER_LIMIT if name == 'pdf/pdf.worker.min.mjs' else MAX_FILE


def check_public_tree(root):
    root = Path(root)
    paths = {}
    if root.is_symlink() or not root.is_dir():
        raise ValueError("public Studio directory must be a regular directory")
    for path in root.rglob("*"):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        relative = path.relative_to(root).as_posix()
        if (relative not in FILES or not stat.S_ISREG(info.st_mode) or
                info.st_nlink != 1 or not 0 < info.st_size <= asset_limit(relative)):
            raise ValueError("public Studio contains an unreviewed or unsupported asset")
        paths[relative] = path
    if paths.keys() != set(FILES):
        raise ValueError("public Studio assets are incomplete")
    return paths
