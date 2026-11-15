#!/usr/bin/env python3
"""Disposable real-Ed25519 custodian export / host-loss / recovery regression."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent
TRUST = ROOT / "workspace-trust.py"
WITNESS = ROOT / "workspace-offsite-witness.py"
CUSTODIAN = ROOT / "workspace-witness-custodian.py"
RECOVERY = ROOT / "workspace-witness-recovery.py"


def call(tool, *args, success=True):
    command = [sys.executable, str(tool), *map(str, args)]
    p = subprocess.run(command, text=True, capture_output=True, timeout=50)
    assert (p.returncode == 0) == success, (
        f"unexpected status={p.returncode} expected success={success}, "
        f"command={command}, out={p.stdout!r}, err={p.stderr!r}"
    )
    return p


def keypair(root, label):
    private = root / (label + ".pem")
    public = root / (label + ".pub.pem")
    subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519",
                    "-out", str(private)], check=True, capture_output=True)
    os.chmod(private, 0o600)
    subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout",
                    "-out", str(public)], check=True, capture_output=True)
    return private, public


def main():
    with tempfile.TemporaryDirectory(prefix="nexus-custodian-recovery-") as td:
        root = Path(td)
        source = root / "source-trust"
        receiver = root / "receiver"
        offhost = root / "independently-retained"
        offhost.mkdir(mode=0o700)
        data_private, data_public = keypair(root, "data-1")
        data_private2, data_public2 = keypair(root, "data-2")
        data_private3, data_public3 = keypair(root, "data-3")
        witness_private, witness_public = keypair(root, "source-witness")
        ack_private, ack_public = keypair(root, "receiver-ack")
        rogue_private, rogue_public = keypair(root, "rogue")

        call(TRUST, "init", "--state-dir", source)
        call(TRUST, "enroll", "--state-dir", source, "--key-id",
             "data-1", "--public-key", data_public)
        call(CUSTODIAN, "init", "--store", receiver,
             "--receiver-id", "independent-disaster-recipient",
             "--source-key-id", "source-witness",
             "--source-public-key", witness_public,
             "--ack-key-id", "receiver-ack",
             "--ack-public-key", ack_public)

        pins = [
            "--expected-receiver-id", "independent-disaster-recipient",
            "--trusted-source-key-id", "source-witness",
            "--trusted-source-public-key", witness_public,
            "--trusted-ack-key-id", "receiver-ack",
            "--trusted-ack-public-key", ack_public,
        ]

        def receipt(label):
            path = root / (label + ".receipt.json")
            call(WITNESS, "seal", "--state-dir", source,
                 "--witness-key-id", "source-witness",
                 "--witness-private-key", witness_private, "--output", path)
            return path

        def acknowledge(path):
            return json.loads(call(
                CUSTODIAN, "receive", "--store", receiver,
                "--receipt", path, "--ack-private-key", ack_private
            ).stdout)

        def retain(label, package):
            path = offhost / (label + ".acknowledged.json")
            path.write_text(json.dumps(package, ensure_ascii=False))
            os.chmod(path, 0o600)
            return path

        first = receipt("first")
        cp1 = retain("checkpoint1", acknowledge(first))
        backup1 = offhost / "backup1.json"
        call(RECOVERY, "export", "--store", receiver,
             "--backup", backup1, "--trusted-checkpoint", cp1,
             "--minimum-sequence", "1", *pins)
        assert backup1.stat().st_mode & 0o077 == 0
        assert "PRIVATE KEY" not in backup1.read_text()
        call(RECOVERY, "export", "--store", receiver,
             "--backup", backup1, "--trusted-checkpoint", cp1,
             "--minimum-sequence", "1", *pins, success=False)

        call(TRUST, "enroll", "--state-dir", source, "--key-id",
             "data-2", "--public-key", data_public2)
        second = receipt("second")
        cp2_obj = acknowledge(second)
        cp2 = retain("checkpoint2", cp2_obj)
        backup2 = offhost / "backup2.json"
        call(RECOVERY, "export", "--store", receiver,
             "--backup", backup2, "--trusted-checkpoint", cp2,
             "--minimum-sequence", "2", *pins)
        call(RECOVERY, "export", "--store", receiver,
             "--backup", offhost / "stale-export.json",
             "--trusted-checkpoint", cp1, "--minimum-sequence", "1",
             *pins, success=False)
        assert not (offhost / "stale-export.json").exists()

        def restore(path, backup=backup2, checkpoint=cp2, floor=2,
                    override=None, success=True):
            keys = pins if override is None else override
            return call(RECOVERY, "restore", "--new-store", path,
                        "--backup", backup, "--trusted-checkpoint", checkpoint,
                        "--minimum-sequence", str(floor),
                        *keys, success=success)

        # An earlier internally valid, genuinely signed ledger must NOT be
        # restored if a later externally retained acknowledgment exists.
        stale = root / "rollback-target"
        restore(stale, backup=backup1, success=False)
        assert not stale.exists()
        restore(stale, backup=backup1, checkpoint=cp1, floor=2, success=False)
        assert not stale.exists()
        wrong_keys = pins.copy()
        wrong_keys[wrong_keys.index("--trusted-ack-public-key") + 1] = rogue_public
        restore(root / "wrong-signer", override=wrong_keys, success=False)
        assert not (root / "wrong-signer").exists()

        def invalid_backup(label, fn):
            altered = json.loads(backup2.read_text())
            fn(altered)
            file = offhost / (label + ".json")
            file.write_text(json.dumps(altered))
            os.chmod(file, 0o600)
            target = root / ("rejected-" + label)
            restore(target, backup=file, success=False)
            assert not target.exists()

        invalid_backup("wrong-digest", lambda d:
                       d.__setitem__("store_sha256", "f" * 64))
        invalid_backup("forged-history", lambda d:
                       d["store"]["entries"][0]["ack"].__setitem__("sequence", 44))
        invalid_backup("truncated-ledger", lambda d:
                       d["store"]["entries"].pop())
        invalid_backup("pinned-public-key", lambda d:
                       d["store"].__setitem__("ack_public_der_base64", "AAAA"))
        invalid_backup("unknown-role", lambda d:
                       d.__setitem__("runtime_import", True))
        invalid_backup("empty-ledger", lambda d:
                       d["store"]["entries"].clear())

        duplicate = offhost / "duplicate-keys.json"
        duplicate.write_bytes(backup2.read_bytes().replace(
            b'"schema":', b'"schema":"injected","schema":', 1
        ))
        restore(root / "duplicate-target", backup=duplicate, success=False)

        symlink = offhost / "linked-backup.json"
        symlink.symlink_to(backup2)
        restore(root / "symlink-target", backup=symlink, success=False)
        hardlink = offhost / "hardlink-backup.json"
        os.link(backup2, hardlink)
        restore(root / "hardlink-target", backup=hardlink, success=False)
        hardlink.unlink()

        # Host-loss simulation. Original recipient directory is destroyed,
        # while key custody and independently acknowledged checkpoint survive.
        old_data = receiver / "custodian.json"
        committed = old_data.read_bytes()
        import shutil
        shutil.rmtree(receiver)
        assert not receiver.exists()
        restore(receiver)
        assert receiver.stat().st_mode & 0o077 == 0
        assert (receiver / "custodian.json").read_bytes() == committed
        assert not (receiver / "ack-private.pem").exists()
        assert json.loads(call(CUSTODIAN, "latest", "--store", receiver).stdout) == cp2_obj
        restore(receiver, success=False)  # never overwrite existing state

        # Without independently preserved private custody, receiver is read-only
        # and cannot forge a new acknowledgment or claim recovery is complete.
        call(TRUST, "enroll", "--state-dir", source, "--key-id",
             "data-3", "--public-key", data_public3)
        third = receipt("third")
        missing_key = root / "missing-recipient-private.pem"
        call(CUSTODIAN, "receive", "--store", receiver,
             "--receipt", third, "--ack-private-key", missing_key, success=False)
        assert json.loads(call(CUSTODIAN, "latest", "--store", receiver).stdout) == cp2_obj
        new_ack = acknowledge(third)
        assert new_ack["ack"]["sequence"] == 3
        assert new_ack["ack"]["previous_ack_sha256"] != "0" * 64

        # Fresh recovery on a *vacant* directory cannot silently race and
        # produce two independent receiver histories with the same identity.
        race_target = root / "racing-recovery"
        race_args = [
            sys.executable, str(RECOVERY), "restore",
            "--new-store", str(race_target), "--backup", str(backup2),
            "--trusted-checkpoint", str(cp2), "--minimum-sequence", "2",
            *map(str, pins),
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(
                lambda _: subprocess.run(race_args, capture_output=True, timeout=50).returncode,
                (0, 1)
            ))
        assert sorted(statuses) == [0, 1], statuses
        assert json.loads(call(CUSTODIAN, "latest", "--store", race_target).stdout) == cp2_obj
        print("CUSTODIAN COMPLETE-HOST-LOSS RECOVERY: PASS "
              "(signed history, latest pinned acknowledgment, fail-closed old backup)")


if __name__ == "__main__":
    main()
