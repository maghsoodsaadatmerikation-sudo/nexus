#!/usr/bin/env python3
"""Local synthetic SSH transcript and real Ed25519 receipt interruption tests.

The fake ssh executable tests *client command construction*, signed response
validation and forced-command receiver recovery. This does not test real
OpenSSH host-key verification, SSH encryption or network deployment.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CLIENT = HERE / "workspace-witness-ssh-client.py"
REMOTE = HERE / "workspace-witness-ssh-receiver.py"
CUSTODIAN = HERE / "workspace-witness-custodian.py"
TRUST = HERE / "workspace-trust.py"
WITNESS = HERE / "workspace-offsite-witness.py"

FAKE_SSH = r'''#!/usr/bin/env python3
import os
from pathlib import Path
import subprocess
import sys

args = sys.argv[1:]
if not args or args[-1] not in ("nexus-witness-v1 receive", "nexus-witness-v1 latest"):
    sys.exit(88)
required = {
    "BatchMode=yes", "StrictHostKeyChecking=yes", "IdentitiesOnly=yes",
    "IdentityAgent=none", "ForwardAgent=no", "ClearAllForwardings=yes",
    "ControlMaster=no", "ProxyCommand=none", "ProxyJump=none",
    "PermitLocalCommand=no", "UpdateHostKeys=no",
}
options = {args[i+1] for i, value in enumerate(args[:-1]) if value == "-o"}
if not required <= options or "-T" not in args or "-F" not in args:
    sys.exit(87)
if args[args.index("-F")+1] != "/dev/null":
    sys.exit(86)
if not any(v.startswith("UserKnownHostsFile=") for v in options):
    sys.exit(85)
if not any(v.startswith("GlobalKnownHostsFile=") for v in options):
    sys.exit(84)
if os.environ.get("NEXUS_FAKE_SSH_NO_HOSTKEY") == "1":
    sys.exit(255)
environment = dict(os.environ)
environment["SSH_ORIGINAL_COMMAND"] = args[-1]
environment["SSH_CONNECTION"] = "127.0.0.1 65432 127.0.0.1 22"
response = subprocess.run(
    [sys.executable, environment["NEXUS_TEST_REMOTE_SCRIPT"]],
    input=sys.stdin.buffer.read(16385), capture_output=True, timeout=35,
    env=environment,
)
if os.environ.get("NEXUS_FAKE_SSH_DROP_REPLY") == "1" and response.returncode == 0:
    # Server committed and fsynced but reply disappeared in transit.
    sys.exit(255)
if os.environ.get("NEXUS_FAKE_SSH_REPLACE_REPLY"):
    sys.stdout.buffer.write(Path(os.environ["NEXUS_FAKE_SSH_REPLACE_REPLY"]).read_bytes())
    sys.exit(0)
sys.stdout.buffer.write(response.stdout)
sys.stderr.buffer.write(response.stderr)
sys.exit(response.returncode)
'''


def call(tool, *args, env=None, success=True):
    result = subprocess.run(
        [sys.executable, str(tool), *map(str, args)],
        env=env, capture_output=True, text=True, timeout=45,
    )
    assert (result.returncode == 0) == success, (
        f"{tool.name}: expected={success}, code={result.returncode}, "
        f"stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    return result


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
    with tempfile.TemporaryDirectory(prefix="nexus-ssh-witness-test-") as directory:
        root = Path(directory)
        remote_store = root / "receiver-ledger"
        local_state = root / "nexus-trust"
        inbox = root / "receipt-transfer"
        inbox.mkdir(mode=0o700)
        fake_bin = root / "bin"
        fake_bin.mkdir()
        ssh = fake_bin / "ssh"
        ssh.write_text(FAKE_SSH)
        os.chmod(ssh, 0o700)

        data_key, data_pub = keypair(root, "data")
        data_key2, data_pub2 = keypair(root, "data2")
        source_key, source_pub = keypair(root, "receipt")
        receiver_key, receiver_pub = keypair(root, "receiver")
        rogue_key, rogue_pub = keypair(root, "rogue")
        transport_key = root / "ssh-identity"
        transport_key.write_text("synthetic CI SSH identity; not a real private key")
        os.chmod(transport_key, 0o600)
        known_hosts = root / "pinned-known-hosts"
        known_hosts.write_text("witness.example.invalid ssh-ed25519 synthetic-fingerprint\n")
        os.chmod(known_hosts, 0o600)

        call(TRUST, "init", "--state-dir", local_state)
        call(TRUST, "enroll", "--state-dir", local_state,
             "--key-id", "data-key-1", "--public-key", data_pub)
        call(CUSTODIAN, "init", "--store", remote_store,
             "--receiver-id", "independent-r1",
             "--source-key-id", "witness-r1",
             "--source-public-key", source_pub,
             "--ack-key-id", "ack-r1",
             "--ack-public-key", receiver_pub)

        def seal(name):
            path = inbox / (name + ".json")
            call(WITNESS, "seal", "--state-dir", local_state,
                 "--witness-key-id", "witness-r1",
                 "--witness-private-key", source_key,
                 "--output", path)
            return path

        environment = dict(os.environ)
        environment["PATH"] = str(fake_bin) + os.pathsep + environment.get("PATH", "")
        environment["NEXUS_TEST_REMOTE_SCRIPT"] = str(REMOTE)
        environment["NEXUS_CUSTODIAN_STORE"] = str(remote_store)
        environment["NEXUS_CUSTODIAN_ACK_KEY"] = str(receiver_key)

        prefix = [
            "--host", "witness.example.invalid",
            "--user", "receiptadmin",
            "--known-hosts", known_hosts,
            "--identity", transport_key,
            "--receiver-id", "independent-r1",
            "--source-key-id", "witness-r1",
            "--source-public-key", source_pub,
            "--ack-key-id", "ack-r1",
            "--ack-public-key", receiver_pub,
            "--state-dir", local_state,
        ]

        first = seal("first")
        output_a = inbox / "accepted-first.json"
        call(CLIENT, "send", *prefix,
             "--minimum-sequence", 1, "--receipt", first,
             "--output", output_a, env=environment)
        package1 = json.loads(output_a.read_text())
        assert package1["ack"]["sequence"] == 1
        assert output_a.stat().st_mode & 0o077 == 0
        # A repeated request is a transparent read-only recovery of only
        # the exact latest receipt, not another accepted event.
        retry = inbox / "recovered-first.json"
        call(CLIENT, "send", *prefix, "--minimum-sequence", 1,
             "--receipt", first, "--output", retry, env=environment)
        assert retry.read_bytes() == output_a.read_bytes()

        wrong_hostfile = inbox / "wrong-host.json"
        absent = root / "missing-known-hosts"
        call(CLIENT, "send", *prefix[:prefix.index("--known-hosts")],
             "--known-hosts", absent,
             *prefix[prefix.index("--identity"):],
             "--minimum-sequence", 1, "--receipt", first,
             "--output", wrong_hostfile, env=environment, success=False)
        assert not wrong_hostfile.exists()
        fake_key = root / "unsafe-identity"
        fake_key.write_bytes(transport_key.read_bytes())
        os.chmod(fake_key, 0o644)
        call(CLIENT, "latest",
             *[fake_key if item == transport_key else item for item in prefix],
             "--minimum-sequence", 1, "--output", wrong_hostfile,
             env=environment, success=False)

        # Simulate both server-side durable commit and loss of the SSH reply.
        call(TRUST, "enroll", "--state-dir", local_state,
             "--key-id", "data-key-2", "--public-key", data_pub2)
        second = seal("second")
        lost = inbox / "reply-lost.json"
        environment["NEXUS_FAKE_SSH_DROP_REPLY"] = "1"
        call(CLIENT, "send", *prefix, "--minimum-sequence", 2,
             "--receipt", second, "--output", lost,
             env=environment, success=False)
        assert not lost.exists()
        latest_after_drop = json.loads(
            call(CUSTODIAN, "latest", "--store", remote_store).stdout
        )
        assert latest_after_drop["ack"]["sequence"] == 2
        environment.pop("NEXUS_FAKE_SSH_DROP_REPLY")
        ack2 = inbox / "retry-after-drop.json"
        call(CLIENT, "send", *prefix, "--minimum-sequence", 2,
             "--receipt", second, "--output", ack2, env=environment)
        assert json.loads(ack2.read_text()) == latest_after_drop
        assert json.loads(call(CUSTODIAN, "latest", "--store", remote_store).stdout)[
            "ack"]["sequence"] == 2

        # A different signed receipt for the same state remains replay.
        same_state = seal("same-state-new-nonce")
        call(CLIENT, "send", *prefix, "--minimum-sequence", 2,
             "--receipt", same_state, "--output", inbox / "replayed.json",
             env=environment, success=False)
        # Old receipts cannot be recovered once a newer state has been stored.
        call(CLIENT, "send", *prefix, "--minimum-sequence", 2,
             "--receipt", first, "--output", inbox / "old.json",
             env=environment, success=False)

        get = inbox / "latest.json"
        call(CLIENT, "latest", *prefix, "--minimum-sequence", 2,
             "--output", get, env=environment)
        assert get.read_bytes() == ack2.read_bytes()
        call(CLIENT, "latest", *prefix, "--minimum-sequence", 3,
             "--output", inbox / "stale.json", env=environment, success=False)

        # The transport may be tricked; a fabricated remote body or wrong
        # custodian key cannot replace independently verified Ed25519.
        forged = inbox / "forged.json"
        fake_package = json.loads(get.read_text())
        fake_package["ack"]["signature_base64"] = "AAAA"
        forged.write_text(json.dumps(fake_package))
        environment["NEXUS_FAKE_SSH_REPLACE_REPLY"] = str(forged)
        call(CLIENT, "latest", *prefix, "--minimum-sequence", 2,
             "--output", inbox / "forged-out.json",
             env=environment, success=False)
        environment.pop("NEXUS_FAKE_SSH_REPLACE_REPLY")
        environment["NEXUS_FAKE_SSH_NO_HOSTKEY"] = "1"
        call(CLIENT, "latest", *prefix, "--minimum-sequence", 2,
             "--output", inbox / "no-hostkey.json",
             env=environment, success=False)
        environment.pop("NEXUS_FAKE_SSH_NO_HOSTKEY")

        # Deny a remote command that the forced SSH entrypoint does not know.
        direct_env = dict(environment)
        direct_env["SSH_CONNECTION"] = "127.0.0.1 100 127.0.0.1 22"
        direct_env["SSH_ORIGINAL_COMMAND"] = "nexus-witness-v1 read-secrets"
        call(REMOTE, env=direct_env, success=False)
        direct_env.pop("SSH_CONNECTION")
        direct_env["SSH_ORIGINAL_COMMAND"] = "nexus-witness-v1 latest"
        call(REMOTE, env=direct_env, success=False)

        assert not (inbox / "forged-out.json").exists()
        assert not (inbox / "no-hostkey.json").exists()
        print("AUTHENTICATED SSH HANDOFF CONTRACT: PASS (synthetic SSH driver; no real network)")


if __name__ == "__main__":
    main()
