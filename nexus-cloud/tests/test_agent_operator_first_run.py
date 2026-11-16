"""Phase 23: installed launcher and Linux atomic no-clobber acceptance."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "scripts/nexus-operator-distribution.py"
SPEC = importlib.util.spec_from_file_location("nexus_distributor_phase23", FILE)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


@pytest.fixture
def installed(tmp_path):
    if os.getuid() == 0:
        pytest.skip("needs a real nonroot account")
    bundle = tmp_path / "pilot.zip"
    built = mod.build(ROOT, bundle)
    dest = tmp_path / "installed"
    outcome = mod.install(bundle, dest, expected_sha256=built["archive_sha256"])
    assert outcome["status"] == "installed-not-executed"
    assert outcome["archive_digest_matched"] is True
    assert outcome["publisher_authenticated"] is False
    return dest, bundle, built


def execute(installation, *args, env=None):
    return subprocess.run([sys.executable, "-I", "-B",
        str(installation / "scripts/nexus-operator-launch.py"), *args],
        capture_output=True, text=True, timeout=20, env=env)


def test_installed_doctor_smoke_preserve_every_file(installed):
    target, _, _ = installed
    good = execute(target, "doctor")
    assert good.returncode == 0, good.stderr
    obj = json.loads(good.stdout)
    assert obj["status"] == "installed-pilot-ready-not-attested"
    assert obj["publisher_authenticated"] is False
    assert obj["execution_performed"] is False
    assert obj["installed_files_verified"] == len(mod.FILES)
    smoke = execute(target, "smoke", "--approve-disposable")
    assert smoke.returncode == 0, smoke.stderr
    result = json.loads(smoke.stdout)
    assert result["status"] == "disposable-smoke-passed"
    assert result["result"]["one_use_replay_denied"] is True
    assert result["result"]["source_project_changed"] is False
    assert result["production_ready"] is False
    assert mod.installed_verify(target)["status"] == "installed-integrity-verified"


def test_launcher_refuses_implicit_consent(installed):
    target, _, _ = installed
    result = execute(target, "smoke")
    assert result.returncode == 2 and not result.stdout
    assert json.loads(result.stderr)["status"] == "denied"
    assert mod.installed_verify(target)["status"] == "installed-integrity-verified"


def test_launcher_rejects_tampered_installed_code(installed):
    target, _, _ = installed
    script = target / "nexus-cloud/agent_operator_pilot.py"
    script.write_bytes(script.read_bytes() + b"\n# altered\n")
    denied = execute(target, "smoke", "--approve-disposable")
    assert denied.returncode == 2 and not denied.stdout
    assert "installed-integrity-unverifiable" in denied.stderr


def test_launcher_refuses_wrong_flags(installed):
    target, _, _ = installed
    for args in [("doctor", "--approve-disposable"), ("smoke", "--root", "/tmp"),
                 ("check",), ("check", "--root", "/tmp", "--approve-disposable")]:
        result = execute(target, *args)
        assert result.returncode == 2 and not result.stdout, args


def test_launcher_python_isolation_and_nonexecuting_check(installed, tmp_path):
    target, _, _ = installed
    root = tmp_path / "operator-root"
    root.mkdir(mode=0o700)
    env = {**os.environ, "PYTHONPATH": "/nonexistent/hijack",
           "PYTHONINSPECT": "1", "PYTHONSTARTUP": "/nonexistent/startup"}
    checked = execute(target, "check", "--root", str(root), env=env)
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)["status"] == "preflight-clear-not-attested"
    assert not (root / ".nexus-operator.token").exists()
    assert sorted(p.name for p in root.iterdir()) == [".nexus-agent-host-admission.lock"]
    assert mod.installed_verify(target)["status"] == "installed-integrity-verified"


def test_atomic_install_refuses_raced_existing_directory(tmp_path, monkeypatch):
    if os.getuid() == 0:
        pytest.skip("needs nonroot")
    bundle = tmp_path / "pilot.zip"
    built = mod.build(ROOT, bundle)
    destination = tmp_path / "installed"
    original = mod._publish_no_replace
    def race(stage, target):
        target.mkdir(mode=0o700)
        (target / "user-file.txt").write_text("preserve")
        return original(stage, target)
    monkeypatch.setattr(mod, "_publish_no_replace", race)
    with pytest.raises(mod.DistributionDenied, match="destination-exists-no-overwrite"):
        mod.install(bundle, destination, expected_sha256=built["archive_sha256"])
    assert (destination / "user-file.txt").read_text() == "preserve"
    assert not any(p.name.startswith(".nexus-pilot-stage-") for p in tmp_path.iterdir())


def test_atomic_install_refuses_raced_symlink(tmp_path, monkeypatch):
    if os.getuid() == 0:
        pytest.skip("needs nonroot")
    bundle = tmp_path / "pilot.zip"
    built = mod.build(ROOT, bundle)
    destination = tmp_path / "installed"
    protected = tmp_path / "protected"
    protected.mkdir(mode=0o700)
    (protected / "note").write_text("original")
    original = mod._publish_no_replace
    def race(stage, target):
        target.symlink_to(protected, target_is_directory=True)
        return original(stage, target)
    monkeypatch.setattr(mod, "_publish_no_replace", race)
    with pytest.raises(mod.DistributionDenied, match="destination-exists-no-overwrite"):
        mod.install(bundle, destination, expected_sha256=built["archive_sha256"])
    assert destination.is_symlink()
    assert (protected / "note").read_text() == "original"


def test_external_hash_match_never_forges_publisher_identity(installed):
    _, bundle, built = installed
    matching = mod.verify(bundle, expected_sha256=built["archive_sha256"])
    assert matching["archive_digest_matched"] is True
    assert matching["publisher_authenticated"] is False
    no_external_hash = mod.verify(bundle)
    assert no_external_hash["archive_digest_matched"] is False
    assert no_external_hash["publisher_authenticated"] is False
