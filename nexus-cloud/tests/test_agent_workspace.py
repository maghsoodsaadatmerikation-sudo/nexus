"""Standalone tests: do not require Docker, a model, network or production keys."""
import os
import pathlib
import stat
import sys
import tempfile
import zipfile
from unittest import mock

import pytest
from agent_workspace import (MAX_FILE_BYTES, Workspace, WorkspaceDenied,
                             run_container, safe_parts)


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    return Workspace(root, "trial")


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "a/../../b", "./a", "a//b", "a/", "", "a\\b", "a\x00b", "x"*513])
def test_path_traversal_rejected(path):
    with pytest.raises(WorkspaceDenied):
        safe_parts(path)


def test_files_persist_between_instances(ws):
    ws.write("src/main.rs", b"fn main() {}", create_parents=True)
    next_session = Workspace(ws.root, ws.name)
    assert next_session.read("src/main.rs") == b"fn main() {}"
    next_session.edit("src/main.rs", b"main()", b"main() /* reviewed */")
    assert ws.read("src/main.rs") == b"fn main() /* reviewed */ {}"


def test_edits_require_single_exact_match_and_preserve_data(ws):
    ws.write("a.txt", b"repeat repeat")
    with pytest.raises(WorkspaceDenied, match="exactly-one"):
        ws.edit("a.txt", b"repeat", b"replace")
    assert ws.read("a.txt") == b"repeat repeat"


def test_file_and_directory_symlink_escape_denied(ws, tmp_path):
    secret = tmp_path / "secret"
    secret.write_text("SECRET")
    (ws.path / "link").symlink_to(secret)
    (ws.path / "dirlink").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        ws.read("link")
    with pytest.raises(WorkspaceDenied):
        ws.write("link", b"attack")
    with pytest.raises(OSError):
        ws.write("dirlink/secret", b"attack")
    assert secret.read_text() == "SECRET"


def test_fifo_and_hardlinks_rejected(ws):
    os.mkfifo(ws.path / "pipe")
    with pytest.raises(WorkspaceDenied):
        ws.read("pipe")
    ws.write("original", b"x")
    os.link(ws.path / "original", ws.path / "alias")
    with pytest.raises(WorkspaceDenied):
        ws.read("alias")
    with pytest.raises(WorkspaceDenied):
        ws.write("original", b"y")


def test_size_bounds_and_private_permissions(ws):
    with pytest.raises(WorkspaceDenied):
        ws.write("large", b"x" * (MAX_FILE_BYTES + 1))
    ws.write("small", b"bytes")
    assert stat.S_IMODE((ws.path / "small").stat().st_mode) == 0o600
    (ws.path / "large").write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    with pytest.raises(WorkspaceDenied):
        ws.read("large")


def test_package_and_symlink_refusal(ws, tmp_path):
    ws.write("docs/readme.txt", b"NEXUS", create_parents=True)
    out = tmp_path / "result.zip"
    receipt = ws.package(out)
    assert receipt["files"] == 1
    with zipfile.ZipFile(out) as z:
        assert z.namelist() == ["docs/readme.txt"]
        assert z.read("docs/readme.txt") == b"NEXUS"
    (ws.path / "bad").symlink_to("/etc/passwd")
    with pytest.raises(WorkspaceDenied):
        ws.package(tmp_path / "rejected.zip")
    assert not (tmp_path / "rejected.zip").exists()


def test_invalid_root_and_workspace(tmp_path):
    root = tmp_path / "root"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    with pytest.raises(WorkspaceDenied):
        Workspace(root, "../escape")
    link = tmp_path / "link"
    link.symlink_to(root)
    with pytest.raises(WorkspaceDenied):
        Workspace(link, "okay")
    root.chmod(0o755)
    with pytest.raises(WorkspaceDenied):
        Workspace(root, "okay")


def test_denies_execution_without_approval_or_pinned_image(ws):
    with pytest.raises(WorkspaceDenied, match="approval"):
        run_container(ws, "python:latest", ["python"], approved=False)
    with pytest.raises(WorkspaceDenied, match="digest-pinned"):
        run_container(ws, "python:latest", ["python"], approved=True)
    with pytest.raises(WorkspaceDenied, match="invalid-command"):
        run_container(ws, "repo@sha256:"+"a"*64, ["\x00"], approved=True)


def test_container_argv_is_hardened_and_non_shell(ws):
    image = "python@sha256:" + "b" * 64
    captured = {}

    class Pipe:
        def __init__(self):
            self.r,self.w = os.pipe()
            os.close(self.w)
        def fileno(self):
            return self.r

    class Process:
        returncode = 0
        def __init__(self, args, **kwargs):
            captured["args"] = args
            self.stdout = Pipe()
            self.stderr = Pipe()
        def wait(self, timeout=None):
            return 0
        def poll(self):
            return 0

    with mock.patch("agent_workspace.os.getuid", return_value=1001), \
         mock.patch("agent_workspace.os.getgid", return_value=1002), \
         mock.patch("agent_workspace.shutil.which", return_value="/usr/bin/docker"), \
         mock.patch("agent_workspace.subprocess.Popen", side_effect=Process):
        receipt = run_container(ws, image, ["python", "-c", "print('ok')"], approved=True)
    args = captured["args"]
    assert receipt.status == "complete" and receipt.exit_code == 0
    assert args[-4:] == [image, "python", "-c", "print('ok')"]
    assert args[args.index("--network")+1] == "none"
    assert args[args.index("--user")+1] == "1001:1002"
    assert "--read-only" in args and "--cap-drop" in args and "--security-opt" in args
    assert not any("docker.sock" in a for a in args)


def test_rejects_comma_in_root_docker_mount_source(tmp_path):
    root = tmp_path / "unsafe,volume"
    root.mkdir(mode=0o700)
    with pytest.raises(WorkspaceDenied):
        Workspace(root, "trial")


def test_manifest_is_deterministic_and_includes_hidden_files_and_empty_directories(ws):
    (ws.path / "empty").mkdir()
    ws.write(".hidden", b"private")
    ws.write("src/x.py", b"print(1)", create_parents=True)
    first = ws.manifest()
    second = Workspace(ws.root, ws.name).manifest()
    assert first == second
    assert first["file_count"] == 2 and first["directory_count"] == 2
    assert first["total_bytes"] == len(b"privateprint(1)")
    assert sorted(x["path"] for x in first["files"]) == [".hidden", "src/x.py"]
    assert all(len(x["sha256"]) == 64 for x in first["files"])
    ws.write("src/x.py", b"print(2)")
    assert ws.manifest()["sha256"] != first["sha256"]
    ws.write("src/x.py", b"print(1)")
    (ws.path / "another-empty").mkdir()
    assert ws.manifest()["sha256"] != first["sha256"]


def test_manifest_rejects_symlink_hardlink_and_fifo(ws):
    ws.write("actual", b"safe")
    os.link(ws.path / "actual", ws.path / "alias")
    with pytest.raises(WorkspaceDenied, match="hardlinks"):
        ws.manifest()
    (ws.path / "alias").unlink()
    (ws.path / "link").symlink_to("actual")
    with pytest.raises(WorkspaceDenied, match="links-and-special"):
        ws.manifest()
    (ws.path / "link").unlink()
    os.mkfifo(ws.path / "fifo")
    with pytest.raises(WorkspaceDenied, match="links-and-special"):
        ws.manifest()


def test_manifest_limits_large_files_and_directory_fanout(ws):
    (ws.path / "oversize").write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    with pytest.raises(WorkspaceDenied, match="large-files"):
        ws.manifest()
    (ws.path / "oversize").unlink()
    for idx in range(401):
        (ws.path / f"d{idx:03}").mkdir()
    with pytest.raises(WorkspaceDenied, match="entry-limit"):
        ws.manifest()


def test_malformed_unicode_path_rejected_instead_of_unicode_exception():
    with pytest.raises(WorkspaceDenied, match="encoding"):
        safe_parts("folder/\ud800")
