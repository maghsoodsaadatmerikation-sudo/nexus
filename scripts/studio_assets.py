"""Public Studio asset contract shared by build, package and release checks."""

MAX_ASSET_BYTES = 480_000
MAX_ARCHIVE_BYTES = 900_000
CORE_ASSETS = (
    "index.html",
    "service-worker.js",
    "manifest.json",
    "icons/nexus-192.png",
    "icons/nexus-512.png",
)
OFFLINE_DEVICE_ASSETS = (
    "device/device-engine.js",
    "device/device-ui.js",
    "device/device-worker.js",
    "device/model-manifest.json",
)
OBSERVED_ASSETS = CORE_ASSETS + OFFLINE_DEVICE_ASSETS
PUBLIC_ASSETS = OBSERVED_ASSETS + (
    "device/vendor/LICENSE-jinja.txt",
    "device/vendor/LICENSE-onnxruntime.txt",
    "device/vendor/LICENSE-transformers.txt",
    "device/vendor/ort-wasm-simd-threaded.asyncify.mjs",
)
