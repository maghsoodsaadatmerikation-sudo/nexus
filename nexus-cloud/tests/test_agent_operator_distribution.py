"""Phase 22: deterministic private operator bundle, digest gating and installed smoke."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import zipfile

import pytest

SOURCE = Path(__file__).resolve().parents[2]
BUILDER = SOURCE / "scripts" / "nexus-operator-distribution.py"
spec = importlib.util.spec_from_file_location("nexus_distribution", BUILDER)
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


def package(tmp_path):
    first=tmp_path/"a.zip"
    result=distribution.build(SOURCE, first)
    return first, result


def test_reproducible_bundle_is_exact_and_nonexecutable(tmp_path):
    first, report=package(tmp_path)
    second=tmp_path/"b.zip"
    other=distribution.build(SOURCE, second)
    assert first.read_bytes()==second.read_bytes()
    assert report["archive_sha256"]==other["archive_sha256"]
    assert report["file_count"]==len(distribution.FILES)
    assert report["publisher_authenticated"] is False
    assert report["production_ready"] is False
    assert first.stat().st_mode & 0o077==0
    with zipfile.ZipFile(first) as z:
        assert set(z.namelist())==set(distribution.FILES)|{distribution.MANIFEST}
        assert all(not x.is_dir() and x.compress_type==zipfile.ZIP_STORED
                   for x in z.infolist())
    with pytest.raises(distribution.DistributionDenied,match="bundle-output"):
        distribution.build(SOURCE, first)


def test_verify_rejects_tampered_archive_even_when_zip_itself_is_readable(tmp_path):
    first, report=package(tmp_path)
    first.write_bytes(first.read_bytes()+b"malicious-trailing-content")
    with pytest.raises(distribution.DistributionDenied,match="archive-sha-mismatch"):
        distribution.verify(first, expected_sha256=report["archive_sha256"])
    # Self-contained hashes are only an integrity tool, not a publisher signature.
    assert distribution.verify(first)["publisher_authenticated"] is False


def test_verify_rejects_extra_member_and_duplicate_names(tmp_path):
    archive,_=package(tmp_path)
    malicious=tmp_path/"extra.zip"
    with zipfile.ZipFile(archive) as good, zipfile.ZipFile(malicious,"w") as z:
        for entry in good.infolist():
            z.writestr(entry, good.read(entry.filename))
        z.writestr("etc/passwd", b"malicious")
    with pytest.raises(distribution.DistributionDenied,match="unexpected-bundle-entry"):
        distribution.verify(malicious)
    repeated=tmp_path/"repeat.zip"
    with zipfile.ZipFile(archive) as good, zipfile.ZipFile(repeated,"w") as z:
        for entry in good.infolist():
            z.writestr(entry, good.read(entry.filename))
        z.writestr(good.infolist()[0], good.read(good.infolist()[0].filename))
    with pytest.raises(distribution.DistributionDenied,match="unexpected-bundle-entry"):
        distribution.verify(repeated)


def test_verify_rejects_changed_file_without_updated_manifest(tmp_path):
    archive,_=package(tmp_path)
    wrong=tmp_path/"wrong.zip"
    target=distribution.FILES[0]
    with zipfile.ZipFile(archive) as good, zipfile.ZipFile(wrong,"w") as z:
        for entry in good.infolist():
            blob=good.read(entry.filename)
            if entry.filename==target:
                blob+=b"\n# changed content\n"
            z.writestr(entry,blob)
    with pytest.raises(distribution.DistributionDenied,match="bundle-manifest-hash-mismatch"):
        distribution.verify(wrong)


def test_verify_rejects_symlink_entries(tmp_path):
    archive,_=package(tmp_path)
    wrong=tmp_path/"linked.zip"
    with zipfile.ZipFile(archive) as good, zipfile.ZipFile(wrong,"w") as z:
        for entry in good.infolist():
            if entry.filename==distribution.FILES[0]:
                entry.external_attr=(stat.S_IFLNK | 0o777)<<16
            z.writestr(entry,good.read(entry.filename))
    with pytest.raises(distribution.DistributionDenied,match="unsafe-bundle-entry"):
        distribution.verify(wrong)


def test_verify_rejects_noncanonical_and_fake_manifest(tmp_path):
    archive,_=package(tmp_path)
    wrong=tmp_path/"bad-manifest.zip"
    with zipfile.ZipFile(archive) as good, zipfile.ZipFile(wrong,"w") as z:
        for entry in good.infolist():
            blob=good.read(entry.filename)
            if entry.filename==distribution.MANIFEST:
                blob=blob.replace(b'"authenticated":false',b'"authenticated":true')
            z.writestr(entry,blob)
    with pytest.raises(distribution.DistributionDenied,match="invalid-bundle-manifest"):
        distribution.verify(wrong)


@pytest.mark.skipif(os.getuid()==0,reason="installation requires nonroot OS user")
def test_private_install_and_smoke_from_installed_tree(tmp_path):
    archive, report=package(tmp_path)
    target=tmp_path/"installed"
    installed=distribution.install(archive,target,
                expected_sha256=report["archive_sha256"])
    assert installed["status"]=="installed-not-executed"
    assert installed["production_ready"] is False
    assert distribution.installed_verify(target)["status"]=="installed-integrity-verified"
    assert target.stat().st_mode & 0o077==0
    assert not (target/".nexus-operator.token").exists()
    assert not (target/"acceptance").exists()
    cli=target/"scripts"/"nexus-operator-pilot.py"
    result=subprocess.run([sys.executable,"-B",str(cli),"smoke","--approve-disposable"],
                          capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)["status"]=="disposable-operator-cycle-passed"
    assert distribution.installed_verify(target)["status"]=="installed-integrity-verified"
    with pytest.raises(distribution.DistributionDenied,match="destination-exists"):
        distribution.install(archive,target,expected_sha256=report["archive_sha256"])


@pytest.mark.skipif(os.getuid()==0,reason="installation requires nonroot OS user")
def test_install_requires_independent_sha_not_archive_manifest(tmp_path):
    archive,report=package(tmp_path)
    target=tmp_path/"installed"
    with pytest.raises(distribution.DistributionDenied,match="archive-sha-mismatch"):
        distribution.install(archive,target,expected_sha256="0"*64)
    assert not target.exists()
    cli=subprocess.run([sys.executable,str(BUILDER),"install","--archive",str(archive),
                        "--destination",str(target)],
                       capture_output=True,text=True,timeout=6)
    assert cli.returncode==2 and not target.exists()
    assert "production_ready" in cli.stderr


@pytest.mark.skipif(os.getuid()==0,reason="installation requires nonroot OS user")
def test_install_refuses_public_parent_and_symlink_path(tmp_path):
    archive,report=package(tmp_path)
    root=tmp_path/"public"
    root.mkdir(mode=0o755)
    with pytest.raises(distribution.DistributionDenied,match="private-0700"):
        distribution.install(archive,root/"installed",
                             expected_sha256=report["archive_sha256"])
    alias=tmp_path/"alias"
    alias.symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises((OSError,distribution.DistributionDenied)):
        distribution.install(archive,alias/"installed",
                             expected_sha256=report["archive_sha256"])
    assert not (root/"installed").exists()


@pytest.mark.skipif(os.getuid()==0,reason="installation requires nonroot OS user")
def test_postinstall_edits_and_new_unexpected_files_are_detected(tmp_path):
    archive,report=package(tmp_path)
    target=tmp_path/"installed"
    distribution.install(archive,target,expected_sha256=report["archive_sha256"])
    script=target/"scripts"/"nexus-operator-pilot.py"
    script.write_bytes(script.read_bytes()+b"\n# unauthorized change\n")
    with pytest.raises(distribution.DistributionDenied,match="installed-file-digest"):
        distribution.installed_verify(target)
    script.write_bytes(zipfile.ZipFile(archive).read("scripts/nexus-operator-pilot.py"))
    (target/"unexpected.txt").write_text("not from bundle")
    (target/"unexpected.txt").chmod(0o600)
    with pytest.raises(distribution.DistributionDenied,match="installed-files-changed"):
        distribution.installed_verify(target)


def test_cli_verify_with_digest_and_refuse_unknown_options(tmp_path):
    archive,report=package(tmp_path)
    cmd=[sys.executable,str(BUILDER),"verify","--archive",str(archive),
         "--expected-sha256",report["archive_sha256"]]
    good=subprocess.run(cmd,capture_output=True,text=True,timeout=6)
    assert good.returncode==0,good.stderr
    assert json.loads(good.stdout)["publisher_authenticated"] is False
    assert json.loads(good.stdout)["archive_digest_matched"] is True
    wrong=subprocess.run([*cmd,"--destination",str(tmp_path/"target")],
                         capture_output=True,text=True,timeout=6)
    assert wrong.returncode==2


def test_source_symlink_or_missing_cannot_build(tmp_path):
    root=tmp_path/"incomplete"
    root.mkdir(mode=0o700)
    with pytest.raises((OSError,distribution.DistributionDenied)):
        distribution.build(root,tmp_path/"none.zip")
    assert not (tmp_path/"none.zip").exists()


def test_verify_pins_zip_snapshot_even_when_path_swapped(tmp_path, monkeypatch):
    """Verified ZIP membership must come from the same bytes as the digest."""
    archive, report = package(tmp_path)
    old_reader = distribution._read_archive_snapshot
    replacement = tmp_path / "replacement.zip"
    replacement.write_bytes(b"not-a-trusted-zip")
    def swap_path_after_snapshot(path):
        snapshot = old_reader(path)
        os.replace(replacement, path)
        return snapshot
    monkeypatch.setattr(distribution, "_read_archive_snapshot",
                        swap_path_after_snapshot)
    result = distribution.verify(
        archive, expected_sha256=report["archive_sha256"])
    assert result["archive_sha256"] == report["archive_sha256"]
    assert result["archive_digest_matched"] is True
    assert archive.read_bytes() == b"not-a-trusted-zip"


@pytest.mark.skipif(os.getuid()==0, reason="installation requires nonroot OS user")
def test_install_extracts_only_verified_snapshot_after_path_mutation(tmp_path, monkeypatch):
    """An archive changed after verification cannot change installed code."""
    archive, report = package(tmp_path)
    payload_path = "scripts/nexus-operator-pilot.py"
    with zipfile.ZipFile(archive, "r") as bundle:
        verified_script = bundle.read(payload_path)
    old_verify = distribution._verify_archive_bytes
    def replace_after_verification(raw_zip, *, expected_sha256=None):
        result = old_verify(raw_zip, expected_sha256=expected_sha256)
        archive.write_bytes(b"replaced-after-hash-validation")
        return result
    monkeypatch.setattr(distribution, "_verify_archive_bytes",
                        replace_after_verification)
    destination = tmp_path / "installed-snapshot"
    result = distribution.install(archive, destination,
                                  expected_sha256=report["archive_sha256"])
    assert result["status"] == "installed-not-executed"
    assert (destination / payload_path).read_bytes() == verified_script
    assert distribution.installed_verify(destination)["status"] == "installed-integrity-verified"
    assert archive.read_bytes() == b"replaced-after-hash-validation"


def test_archive_symlink_is_denied_before_digest_validation(tmp_path):
    archive, report = package(tmp_path)
    alias = tmp_path / "archive-alias.zip"
    alias.symlink_to(archive)
    with pytest.raises(OSError):
        distribution.verify(alias, expected_sha256=report["archive_sha256"])


def _copy_allowlisted_source(tmp_path):
    root = tmp_path / "operator-source"
    root.mkdir(mode=0o700)
    for name in distribution.FILES:
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, destination)
    return root


def test_operator_build_rejects_symlinked_source_member(tmp_path):
    root = _copy_allowlisted_source(tmp_path)
    name = distribution.FILES[0]
    member = root / name
    member.unlink()
    member.symlink_to(SOURCE / name)
    output = tmp_path / "symlink-source.zip"
    with pytest.raises((OSError, distribution.DistributionDenied)):
        distribution.build(root, output)
    assert not output.exists()


def test_operator_build_rejects_symlinked_source_directory_and_root(tmp_path):
    root = _copy_allowlisted_source(tmp_path)
    root_link = tmp_path / "source-link"
    root_link.symlink_to(root, target_is_directory=True)
    output = tmp_path / "root-link.zip"
    with pytest.raises((OSError, distribution.DistributionDenied)):
        distribution.build(root_link, output)
    assert not output.exists()
    directory = root / "docs"
    original = root / "docs-original"
    directory.rename(original)
    directory.symlink_to(original, target_is_directory=True)
    with pytest.raises((OSError, distribution.DistributionDenied)):
        distribution.build(root, output)
    assert not output.exists()


def test_operator_build_rejects_source_hardlink(tmp_path):
    root = _copy_allowlisted_source(tmp_path)
    member = root / distribution.FILES[0]
    os.link(member, tmp_path / "same-inode")
    output = tmp_path / "linked-source.zip"
    with pytest.raises(distribution.DistributionDenied,
                       match="source-not-regular-or-too-large"):
        distribution.build(root, output)
    assert not output.exists()


def test_operator_build_rejects_source_member_swap_during_open(tmp_path, monkeypatch):
    """A swapped final path cannot redirect source reads outside checkout."""
    root = _copy_allowlisted_source(tmp_path)
    name = distribution.FILES[0]
    target = root / name
    external = tmp_path / "external-data"
    external.write_text("do-not-include-in-bundle")
    raw_open = os.open
    triggered = False

    def swap_before_open(path, flags, *args, **kwargs):
        nonlocal triggered
        if (not triggered and path == target.name
                and kwargs.get("dir_fd") is not None):
            triggered = True
            target.unlink()
            target.symlink_to(external)
        return raw_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(distribution.os, "open", swap_before_open)
    output = tmp_path / "swapped-source.zip"
    with pytest.raises((OSError, distribution.DistributionDenied)):
        distribution.build(root, output)
    assert triggered
    assert not output.exists()


def test_operator_build_rejects_mutation_during_source_read(tmp_path, monkeypatch):
    root = _copy_allowlisted_source(tmp_path)
    target = root / distribution.FILES[0]
    expected_inode = target.stat().st_ino
    original_read = os.read
    mutated = False

    def mutate_after_read(fd, count):
        nonlocal mutated
        data = original_read(fd, count)
        if data and not mutated and os.fstat(fd).st_ino == expected_inode:
            mutated = True
            with target.open("r+b") as stream:
                stream.seek(0)
                stream.write(b"Z")
                stream.flush()
                os.fsync(stream.fileno())
        return data

    monkeypatch.setattr(distribution.os, "read", mutate_after_read)
    output = tmp_path / "mutated-source.zip"
    with pytest.raises(distribution.DistributionDenied,
                       match="source-mutated-during-build"):
        distribution.build(root, output)
    assert mutated
    assert not output.exists()
