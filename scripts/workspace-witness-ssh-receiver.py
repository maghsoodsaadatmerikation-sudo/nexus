#!/usr/bin/env python3
"""OpenSSH forced-command entrypoint for a separately operated NEXUS custodian.

Configure an authorized_keys forced command to invoke this *without arguments*.
Only two exact SSH_ORIGINAL_COMMAND values are admitted. It relies on the
SSH daemon to authenticate clients and pin host identity in client known_hosts.
No HTTP service, signing-key provision or deployment is performed here.
"""
import os
from pathlib import Path
import sys


def abort():
    print("NEXUS CUSTODIAN SSH REQUEST DENIED", file=sys.stderr)
    return 1


def main():
    action = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    if action not in ("nexus-witness-v1 receive", "nexus-witness-v1 latest"):
        return abort()
    if not os.environ.get("SSH_CONNECTION"):
        return abort()
    store = os.environ.get("NEXUS_CUSTODIAN_STORE", "")
    private = os.environ.get("NEXUS_CUSTODIAN_ACK_KEY", "")
    if not store or not Path(store).is_absolute():
        return abort()
    if action.endswith("receive") and (not private or not Path(private).is_absolute()):
        return abort()
    script = Path(__file__).resolve().with_name("workspace-witness-custodian.py")
    if action.endswith("receive"):
        argv = [
            sys.executable, str(script), "receive-stdin",
            "--store", store, "--ack-private-key", private,
        ]
    else:
        argv = [sys.executable, str(script), "latest", "--store", store]
    os.execv(sys.executable, argv)


if __name__ == "__main__":
    sys.exit(main())
