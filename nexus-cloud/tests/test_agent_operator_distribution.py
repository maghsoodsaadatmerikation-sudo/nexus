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
    assert json.loads(good.stdout)["publisher_authenticated"] is True
    wrong=subprocess.run([*cmd,"--destination",str(tmp_path/"target")],
                         capture_output=True,text=True,timeout=6)
    assert wrong.returncode==2


def test_source_symlink_or_missing_cannot_build(tmp_path):
    root=tmp_path/"incomplete"
    root.mkdir(mode=0o700)
    with pytest.raises((OSError,distribution.DistributionDenied)):
        distribution.build(root,tmp_path/"none.zip")
    assert not (tmp_path/"none.zip").exists()
