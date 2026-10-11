#!/usr/bin/env python3
"""The static gate must reject cleanup outside the dedicated witness mount."""
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
files = [
    "scripts/verify-storage-full.py", "docs/gateway-storage-full.md",
    "scripts/verify-storage-failure-http.py", "docs/gateway-storage-failure.md",
    "Dockerfile", "docs/DEPLOYMENT.md", "scripts/workspace-backup.sh",
    "scripts/workspace-restore.sh", "scripts/readonly-verification.sh",
    "scripts/v1.2-durable-state-resilience.sh",
    "scripts/data-snapshot.py", "docs/full-data-recovery.md", "artifact-05/src/main.rs",
    "artifact-05/src/lib.rs", "scripts/verify-data-recovery-http.py", "docs/gateway-health.md",
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
        ('volume_restore="$RUNNER_TEMP/nexus-full-data-restored-${GITHUB_RUN_ID}"', 'volume_restore="/production"'),
        ('"$volume_restore" --offline --owner', '"$volume_restore" --owner'),
        ('--offline --acknowledge-replay-risk', '--offline'),
        ('"$restored" --quarantined', '"$restored"'),
    ]
    mutations = [("scripts/readonly-verification.sh", old, new) for old, new in mutations]
    mutations.extend([
        ("scripts/verify-storage-full.py", "size=8m", "size=8g"),
        ("scripts/verify-storage-full.py", "'--tmpfs'", "'--volume'"),
        ("scripts/readonly-verification.sh", 'python3 scripts/verify-storage-full.py nexus-ci-smoke "$GITHUB_RUN_ID"', 'true # omitted ENOSPC drill'),
        ("scripts/readonly-verification.sh", "mv /data/requests /data/requests.offline", "mv /production/requests /data/requests.offline"),
        ("scripts/readonly-verification.sh", '"$volume_request_id" restarted', '"$volume_request_id" unavailable'),
        ("Dockerfile", "GET /livez HTTP/1.1", "GET / HTTP/1.1"),
        ("scripts/verify-data-recovery-http.py", '("/readyz", 503 if args.quarantined else 200,',
         '("/readyz", 200 if args.quarantined else 200,'),
        ("artifact-05/src/lib.rs", '.route("/readyz", get(readiness::<D>))',
         '.route("/obsolete-readyz", get(readiness::<D>))'),
    ])
    originals = {name: (fixture / name).read_text() for name in files}
    for name, old, new in mutations:
        for filename, text in originals.items():
            (fixture / filename).write_text(text)
        original = originals[name]
        if old is not None:
            assert old in original
        (fixture / name).write_text(original if old is None else original.replace(old, new))
        result = subprocess.run(
            ["bash", str(fixture / "scripts/v1.2-durable-state-resilience.sh")],
            capture_output=True, text=True, check=False,
        )
        if old is None:
            assert result.returncode == 0, result.stderr
        else:
            assert result.returncode != 0, "unsafe cleanup passed"
            assert "BLOCKED" in result.stderr
print("DURABLE WITNESS CLEANUP CONTRACT: PASS (valid + 15 rejected mutations)")
