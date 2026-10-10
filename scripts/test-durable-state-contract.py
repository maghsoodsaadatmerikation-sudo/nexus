#!/usr/bin/env python3
"""The static gate must reject cleanup outside the dedicated witness mount."""
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
files = [
    "Dockerfile", "docs/DEPLOYMENT.md", "scripts/workspace-backup.sh",
    "scripts/workspace-restore.sh", "scripts/readonly-verification.sh",
    "scripts/v1.2-durable-state-resilience.sh",
]
with tempfile.TemporaryDirectory(prefix="nexus-contract-") as tmp:
    fixture = Path(tmp)
    for name in files:
        destination = fixture / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, destination)
    harness = fixture / "scripts/readonly-verification.sh"
    original = harness.read_text()
    mutations = [
        (None, None),
        ('-v "$smoke_data:/data" nexus-ci-smoke', '-v "/production:/data" nexus-ci-smoke'),
        ('find /data -mindepth 1 -maxdepth 1', 'find /other -mindepth 1 -maxdepth 1'),
        ('find /data -mindepth 1 -maxdepth 1', 'find /data -maxdepth 1'),
    ]
    for old, new in mutations:
        if old is not None:
            assert old in original
        harness.write_text(original if old is None else original.replace(old, new))
        result = subprocess.run(
            ["bash", str(fixture / "scripts/v1.2-durable-state-resilience.sh")],
            capture_output=True, text=True, check=False,
        )
        if old is None:
            assert result.returncode == 0, result.stderr
        else:
            assert result.returncode != 0, "unsafe cleanup passed"
            assert "isolated destructive witness exercise missing" in result.stderr
print("DURABLE WITNESS CLEANUP CONTRACT: PASS (valid + 3 rejected mutations)")
