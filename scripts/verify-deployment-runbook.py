#!/usr/bin/env python3
"""Fail-closed, offline alignment of operator runbook with the Rust gateway.

No provider credentials, network calls, release authorization or mutation.
The check guards a specific current contract; update it deliberately alongside
any future changes to the runtime's readiness behavior.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = (
    "docs/DEPLOYMENT.md",
    "docs/gateway-health.md",
    "artifact-05/src/lib.rs",
    "artifact-05/src/main.rs",
    "artifact-05/src/volume_identity.rs",
    "scripts/data-snapshot.py",
    "scripts/enroll-new-volume.py",
    "artifact-05/src/workspace_api.rs",
    "Dockerfile",
    "render.yaml",
    "scripts/production-freeze-preflight.py",
)
EXPECTED_FAILURE_STATUSES = frozenset({
    "quarantined",
    "storage_unavailable",
    "workspace_unavailable",
    "admission_unavailable",
})


def require(condition: bool, label: str) -> None:
    if not condition:
        raise ValueError(label)


def read_source(relative: str) -> str:
    path = ROOT / relative
    require(path.is_file() and not path.is_symlink(), "missing-or-symlinked-file")
    require(0 < path.stat().st_size <= 256 * 1024, "unbounded-contract-source")
    return path.read_text(encoding="utf-8")


def check(sources: dict[str, str]) -> None:
    for name in FILES:
        require(name in sources and isinstance(sources[name], str), "missing-contract-source")

    runbook = sources["docs/DEPLOYMENT.md"]
    health = sources["docs/gateway-health.md"]
    gateway = sources["artifact-05/src/lib.rs"]
    main = sources["artifact-05/src/main.rs"]
    identity = sources["artifact-05/src/volume_identity.rs"]
    snapshot = sources["scripts/data-snapshot.py"]
    enrollment = sources["scripts/enroll-new-volume.py"]
    api = sources["artifact-05/src/workspace_api.rs"]
    docker = sources["Dockerfile"]
    blueprint = sources["render.yaml"]
    freeze = sources["scripts/production-freeze-preflight.py"]

    require("async fn readiness" in gateway and
            "async fn studio_model_status" in gateway, "missing-readiness-handler")
    handler = gateway.split("async fn readiness", 1)[1].split(
        "async fn studio_model_status", 1)[0]
    found = re.findall(
        r'health_response\(StatusCode::SERVICE_UNAVAILABLE, "([a-z_]+)"\)',
        handler,
    )
    require(len(found) == 4 and set(found) == EXPECTED_FAILURE_STATUSES,
            "readiness-status-contract-changed")
    require('health_response(StatusCode::OK, "ready")' in handler and
            ".check_readiness().is_err()" in handler and
            ".check_storage_readiness().is_err()" in handler and
            "max_tracked_requests" in handler, "readiness-safety-gate-missing")

    require("## Liveness and readiness" in runbook and
            "## Production requirements" in runbook, "runbook-readiness-section-missing")
    section = runbook.split("## Liveness and readiness", 1)[1].split(
        "## Production requirements", 1)[0]
    documented = re.findall(r'^- `([a-z_]+)`\s+—', section, flags=re.MULTILINE)
    require(len(documented) == 4 and set(documented) == set(found),
            "operator-readiness-statuses-out-of-sync")
    require('{"status":"ready"}' in section and
            '{"status":"alive"}' in section and
            "Cache-Control: no-store" in section,
            "operator-readiness-response-details-missing")
    for code in ("503", "409", "422"):
        require(code in section, "operator-http-status-missing")
    for phrase in ("workspace_storage_unavailable", "workspace_already_exists",
                   "ENOSPC", "read-only"):
        require(phrase in section, "operator-readiness-caveat-missing")
    require("reports the recovery gate only" not in runbook,
            "old-false-green-description-returned")
    require(all(x in health for x in EXPECTED_FAILURE_STATUSES),
            "gateway-health-reference-incomplete")

    require("token.bytes().all(|byte| byte.is_ascii_graphic())" in gateway and
            "printable ASCII token without spaces" in runbook and
            "only one unambiguous" in runbook,
            "bearer-startup-validation-undocumented")
    require('with_request_store(data_root.join("requests"))' in main and
            'CoreDelegate::new(data_root.clone())' in main and
            "requests/" in runbook and
            "pins the Workspace directory" in runbook,
            "durable-data-layout-undocumented")
    # The opt-in guard is deliberately checked before any startup code can
    # construct missing data directories or request ledgers. Cold snapshots
    # must preserve its existing marker, not auto-enroll a restored volume.
    require(main.count("volume_identity::verify(&data_root, expected)") == 2 and
            main.index("volume_identity::verify(&data_root, expected)") <
            main.index("CoreDelegate::new(data_root.clone())") and
            "NEXUS_EXPECTED_VOLUME_ID" in main and
            "NEXUS_EXPECTED_VOLUME_ID" in runbook and
            "legacy startup" in runbook and
            "Never enroll" in runbook and
            ".nexus-volume-identity" in identity and
            "O_NOFOLLOW" in identity and
            "VOLUME_IDENTITY_MARKER" in snapshot and
            "elif name == VOLUME_IDENTITY_MARKER:" in snapshot and
            "invalid volume identity marker" in snapshot and
            "if os.listdir(fd)" in enrollment and
            "os.O_EXCL" in enrollment,
            "volume-identity-admission-or-recovery-guard-absent")

    require("workspace_storage_unavailable" in api and
            "workspace_already_exists" in api and
            "StatusCode::CONFLICT" in api and
            "StatusCode::SERVICE_UNAVAILABLE" in api,
            "workspace-http-error-contract-changed")

    require('CMD ["/usr/local/bin/nexus", "--health-check"]' in docker and
            "/usr/local/bin/nexus --health-check" in section,
            "liveness-container-health-mismatch")
    require("healthCheckPath: /" in blueprint and
            "Render Blueprint uses the root" in section,
            "blueprint-health-not-distinguished")
    require('render.get("autoDeploy") != "no"' in freeze and
            'parameters.get("strict_required_status_checks_policy") is not True' in freeze and
            "auto-deploy" in runbook and
            "strict current-base" in runbook,
            "release-freeze-hold-undocumented")
    require("full-volume" in runbook and "synthetic data" in runbook and
            "draft and unmerged" in runbook,
            "release-claim-boundary-not-preserved")


def self_test(sources: dict[str, str]) -> None:
    check(sources)
    mutations = (
        ("docs/DEPLOYMENT.md", "- `workspace_unavailable`",
         "- `removed_status`"),
        ("docs/DEPLOYMENT.md", "printable ASCII token without spaces",
         "arbitrary token accepted"),
        ("docs/DEPLOYMENT.md", "Render Blueprint uses the root",
         "Render Blueprint health proves readiness"),
        ("docs/DEPLOYMENT.md", "draft and unmerged", "ready for merge"),
        ("artifact-05/src/lib.rs", '"workspace_unavailable"',
         '"silently_ready"'),
        ("artifact-05/src/main.rs", 'data_root.join("requests")',
         'data_root.join("untracked")'),
        ("artifact-05/src/main.rs", 'NEXUS_EXPECTED_VOLUME_ID',
         'NEXUS_UNUSED_VOLUME_ID'),
        ("docs/DEPLOYMENT.md", "Never enroll", "Always enroll"),
        ("scripts/data-snapshot.py", 'elif name == VOLUME_IDENTITY_MARKER:',
         'elif name == "ignored-volume-identity":'),
        ("Dockerfile", 'CMD ["/usr/local/bin/nexus", "--health-check"]',
         'CMD ["sh", "-c", "exit 0"]'),
        ("scripts/production-freeze-preflight.py",
         'parameters.get("strict_required_status_checks_policy") is not True',
         'parameters.get("strict_required_status_checks_policy") is not False'),
    )
    for path, before, after in mutations:
        require(before in sources[path], "invalid-self-test-fixture")
        altered = dict(sources)
        altered[path] = sources[path].replace(before, after, 1)
        try:
            check(altered)
        except ValueError:
            continue
        raise ValueError("unsafe-runbook-mutation-accepted")
    print("DEPLOYMENT RUNBOOK NEGATIVE TESTS: PASS")


def main() -> int:
    if len(sys.argv) not in (1, 2) or (
        len(sys.argv) == 2 and sys.argv[1] != "--self-test"
    ):
        return 2
    try:
        sources = {name: read_source(name) for name in FILES}
        check(sources)
        if len(sys.argv) == 2:
            self_test(sources)
    except (ValueError, OSError, UnicodeError):
        print("DEPLOYMENT RUNBOOK CONTRACT: FAIL", file=sys.stderr)
        return 1
    print("DEPLOYMENT RUNBOOK CONTRACT: PASS (no release authority)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
