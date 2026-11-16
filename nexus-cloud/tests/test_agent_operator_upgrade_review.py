"""Phase 24: two installed versions are compared only after independent hash pinning."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

SOURCE = Path(__file__).resolve().parents[2]
BUILDER = SOURCE / "scripts" / "nexus-operator-distribution.py"
spec = importlib.util.spec_from_file_location("nexus_pilot_distribution_compare", BUILDER)
dist = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dist)
nonroot = pytest.mark.skipif(os.getuid() == 0, reason="operator installation requires nonroot")


def bundle(tmp_path, name="pilot.zip", root=SOURCE):
    archive = tmp_path / name
    summary = dist.build(root, archive)
    return archive, summary


def install_two(tmp_path):
    archive, manifest = bundle(tmp_path)
    first = tmp_path / "old"
    second = tmp_path / "new"
    for target in (first, second):
        dist.install(archive, target, expected_sha256=manifest["archive_sha256"])
    return first, second, manifest


@nonroot
def test_identical_private_installations_comparable_without_side_effects(tmp_path):
    old, new, build = install_two(tmp_path)
    original = (old / dist.MANIFEST).read_bytes()
    result = dist.compare_installed(
        old, new, expected_candidate_manifest_sha256=build["manifest_sha256"],
        expected_current_manifest_sha256=build["manifest_sha256"])
    assert result["status"] == "same-file-content"
    assert result["changed_paths"] == []
    assert result["changed_file_count"] == 0
    assert result["candidate_manifest_anchor_matched"] is True
    assert result["previous_manifest_anchor_matched"] is True
    assert result["upgrade_authorized"] is False
    assert result["data_migrated"] is False
    assert result["publisher_authenticated"] is False
    assert (old / dist.MANIFEST).read_bytes() == original
    assert dist.installed_verify(old)["status"] == "installed-integrity-verified"


@nonroot
def test_changed_allowlisted_document_detected_without_execution_or_migration(tmp_path):
    archive, info = bundle(tmp_path, "current.zip")
    old = tmp_path / "installed-current"
    dist.install(archive, old, expected_sha256=info["archive_sha256"])
    root = tmp_path / "variant-source"
    root.mkdir(mode=0o700)
    for name in dist.FILES:
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, destination)
    changed = "docs/PHASE24-SIDE-BY-SIDE-REVIEW.md"
    (root / changed).write_bytes((root / changed).read_bytes() + b"\nVariant review-only documentation.\n")
    variant, variant_info = bundle(tmp_path, "candidate.zip", root=root)
    new = tmp_path / "installed-next"
    dist.install(variant, new, expected_sha256=variant_info["archive_sha256"])
    before = (old / changed).read_bytes()
    result = dist.compare_installed(old, new,
        expected_candidate_manifest_sha256=variant_info["manifest_sha256"],
        expected_current_manifest_sha256=info["manifest_sha256"])
    assert result["status"] == "review-required"
    assert result["changed_paths"] == [changed]
    assert result["changed_file_count"] == 1
    assert result["upgrade_authorized"] is False
    assert (old / changed).read_bytes() == before
    assert (new / changed).read_bytes() != before
    assert not (old / "journal").exists()


@nonroot
def test_wrong_out_of_band_candidate_sha_denied_and_old_install_unchanged(tmp_path):
    old, new, _ = install_two(tmp_path)
    old_content = (old / dist.MANIFEST).read_bytes()
    with pytest.raises(dist.DistributionDenied, match="anchor-mismatch"):
        dist.compare_installed(old, new,
            expected_candidate_manifest_sha256="0" * 64)
    with pytest.raises(dist.DistributionDenied, match="candidate-manifest-sha"):
        dist.compare_installed(old, new,
            expected_candidate_manifest_sha256="")
    assert (old / dist.MANIFEST).read_bytes() == old_content


@nonroot
def test_wrong_old_anchor_or_same_installation_refused(tmp_path):
    old, new, info = install_two(tmp_path)
    with pytest.raises(dist.DistributionDenied, match="anchor-mismatch"):
        dist.compare_installed(old, new,
            expected_current_manifest_sha256="a" * 64,
            expected_candidate_manifest_sha256=info["manifest_sha256"])
    with pytest.raises(dist.DistributionDenied, match="distinct-installations"):
        dist.compare_installed(old, old,
            expected_candidate_manifest_sha256=info["manifest_sha256"])


@nonroot
def test_corrupted_candidate_source_rejected_before_report(tmp_path):
    old, new, info = install_two(tmp_path)
    code = new / "scripts" / "nexus-operator-pilot.py"
    code.write_bytes(code.read_bytes() + b"\n# unauthorized edit\n")
    with pytest.raises(dist.DistributionDenied, match="installed-file-digest"):
        dist.compare_installed(old, new,
            expected_candidate_manifest_sha256=info["manifest_sha256"])
    assert dist.installed_verify(old)["status"] == "installed-integrity-verified"


@nonroot
def test_private_directories_and_single_link_required(tmp_path):
    old, new, info = install_two(tmp_path)
    old.chmod(0o755)
    with pytest.raises(dist.DistributionDenied, match="installation-directory-unsafe"):
        dist.compare_installed(old, new,
            expected_candidate_manifest_sha256=info["manifest_sha256"])
    old.chmod(0o700)
    subdir = new / "nexus-cloud"
    subdir.chmod(0o755)
    with pytest.raises(dist.DistributionDenied, match="installed-directory-unsafe"):
        dist.installed_verify(new)
    subdir.chmod(0o700)
    code = new / "scripts" / "nexus-operator-pilot.py"
    os.link(code, tmp_path / "external-hardlink")
    with pytest.raises(dist.DistributionDenied, match="installed-file-unsafe"):
        dist.installed_verify(new)


@nonroot
def test_symlink_candidate_and_extra_file_denied(tmp_path):
    old, new, info = install_two(tmp_path)
    alias = tmp_path / "symlink-candidate"
    alias.symlink_to(new, target_is_directory=True)
    with pytest.raises(dist.DistributionDenied, match="installation-directory-unsafe"):
        dist.compare_installed(old, alias,
            expected_candidate_manifest_sha256=info["manifest_sha256"])
    extra = new / "scripts" / "foreign.py"
    extra.write_text("private user data")
    extra.chmod(0o600)
    with pytest.raises(dist.DistributionDenied, match="installed-files-changed"):
        dist.compare_installed(old, new,
            expected_candidate_manifest_sha256=info["manifest_sha256"])


@nonroot
def test_installed_launcher_checks_external_digest_before_smoke(tmp_path):
    archive, info = bundle(tmp_path)
    installed = tmp_path / "installed"
    dist.install(archive, installed, expected_sha256=info["archive_sha256"])
    launcher = installed / "scripts" / "nexus-operator-launch.py"
    command = [sys.executable, "-I", "-B", str(launcher)]
    good = subprocess.run([*command, "doctor", "--expected-manifest-sha256",
                           info["manifest_sha256"]],
                          text=True, capture_output=True, timeout=12)
    assert good.returncode == 0, good.stderr
    body = json.loads(good.stdout)
    assert body["manifest_anchor_matched"] is True
    assert body["publisher_authenticated"] is False
    bad = subprocess.run([*command, "smoke", "--approve-disposable",
                          "--expected-manifest-sha256", "0" * 64],
                         text=True, capture_output=True, timeout=10)
    assert bad.returncode == 2
    assert json.loads(bad.stderr)["status"] == "denied"
    assert dist.installed_verify(installed)["status"] == "installed-integrity-verified"


@nonroot
def test_compare_installed_cli_requires_external_candidate_anchor(tmp_path):
    old, new, info = install_two(tmp_path)
    base = [sys.executable, "-I", "-B", str(BUILDER),
            "compare-installed", "--current", str(old), "--candidate", str(new)]
    no_anchor = subprocess.run(base, text=True, capture_output=True, timeout=8)
    assert no_anchor.returncode == 2
    checked = subprocess.run([*base, "--expected-candidate-manifest-sha256",
                              info["manifest_sha256"]],
                             text=True, capture_output=True, timeout=8)
    assert checked.returncode == 0, checked.stderr
    report = json.loads(checked.stdout)
    assert report["status"] == "same-file-content"
    assert report["upgrade_authorized"] is False


@nonroot
def test_pinned_installed_verification_without_mutation(tmp_path):
    archive, info = bundle(tmp_path)
    installed = tmp_path / "installed"
    dist.install(archive, installed, expected_sha256=info["archive_sha256"])
    actual = dist.installed_verify(installed,
        expected_manifest_sha256=info["manifest_sha256"])
    assert actual["manifest_anchor_matched"] is True
    assert actual["manifest_sha256"] == info["manifest_sha256"]
    with pytest.raises(dist.DistributionDenied, match="anchor-mismatch"):
        dist.installed_verify(installed, expected_manifest_sha256="f" * 64)


def synthetic_legacy_install(tmp_path, files, name):
    """A canonical, private old-layout fixture with current controlled bytes."""
    target = tmp_path / name
    target.mkdir(mode=0o700)
    source_entries = []
    for rel in files:
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = (SOURCE / rel).read_bytes()
        dst.write_bytes(payload)
        dst.chmod(0o600)
        source_entries.append({
            "path": rel, "sha256": dist._sha(payload), "bytes": len(payload)})
    manifest = dist._json({
        "schema": dist.SCHEMA, "platform": "linux-nonroot-operator-pilot",
        "minimum_python": "3.13", "authenticated": False,
        "source_files": source_entries})
    metadata = target / dist.MANIFEST
    metadata.write_bytes(manifest)
    metadata.chmod(0o600)
    return target, dist._sha(manifest)


@nonroot
@pytest.mark.parametrize("files,added", [
    (dist._V23_FILES, ["docs/PHASE24-SIDE-BY-SIDE-REVIEW.md"]),
    (dist._V22_FILES, [
        "docs/PHASE23-VERIFIED-FIRST-RUN.md",
        "docs/PHASE24-SIDE-BY-SIDE-REVIEW.md",
        "scripts/nexus-operator-launch.py",
    ]),
])
def test_prior_audited_installed_file_layouts_are_reviewable(tmp_path, files, added):
    prior, prior_sha = synthetic_legacy_install(tmp_path, files, "historical")
    archive, info = bundle(tmp_path)
    next_version = tmp_path / "candidate"
    dist.install(archive, next_version, expected_sha256=info["archive_sha256"])
    report = dist.compare_installed(
        prior, next_version, expected_current_manifest_sha256=prior_sha,
        expected_candidate_manifest_sha256=info["manifest_sha256"])
    assert report["status"] == "review-required"
    assert report["added_paths"] == sorted(added)
    assert report["removed_paths"] == []
    assert report["modified_paths"] == []
    assert report["previous_file_count"] == len(files)
    assert report["candidate_file_count"] == len(dist.FILES)
    assert report["upgrade_authorized"] is False
    assert dist.installed_verify(prior, expected_manifest_sha256=prior_sha)["file_count"] == len(files)


@nonroot
def test_previous_version_removal_direction_is_reported_not_applied(tmp_path):
    old_version, old_sha = synthetic_legacy_install(
        tmp_path, dist._V23_FILES, "previous")
    archive, info = bundle(tmp_path)
    current = tmp_path / "current"
    dist.install(archive, current, expected_sha256=info["archive_sha256"])
    report = dist.compare_installed(current, old_version,
        expected_current_manifest_sha256=info["manifest_sha256"],
        expected_candidate_manifest_sha256=old_sha)
    assert report["removed_paths"] == ["docs/PHASE24-SIDE-BY-SIDE-REVIEW.md"]
    assert report["added_paths"] == []
    assert report["upgrade_authorized"] is False
    assert (current / "docs/PHASE24-SIDE-BY-SIDE-REVIEW.md").exists()


@nonroot
def test_unrecognized_old_manifest_file_inventory_fails_closed(tmp_path):
    suspicious = tuple(p for p in dist._V23_FILES
                       if p != "scripts/nexus-engineering-plan.py")
    target, sha = synthetic_legacy_install(tmp_path, suspicious, "unknown")
    with pytest.raises(dist.DistributionDenied, match="unknown-installed-file-layout"):
        dist.installed_verify(target, expected_manifest_sha256=sha)
