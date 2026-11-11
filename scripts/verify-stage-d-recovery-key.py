#!/usr/bin/env python3
"""Owner-local fail-closed decryption drill for the pinned Stage D recovery key.

Never copies a private key or workspace data to GitHub, Railway, or stdout.
Run only on a trusted, owner-controlled local machine, NOT CI/cloud runners.
"""
import argparse
import hashlib
import hmac
import os
import shutil
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
CERT = REPO / "docs/keys/stage-d-recovery-public-cert.pem"
CERT_SHA256 = "b27cc7a84e333fce78f790dce20335258b11e724bac1a91b3b7c886ac3812091"
OPENSSL = Path(shutil.which("openssl") or "/nonexistent/nexus-openssl")


class KeyCheckBlocked(ValueError):
    pass


def require(ok):
    if not ok:
        raise KeyCheckBlocked("recovery-key local proof blocked")


def prove(key, cert=CERT, pinned_digest=CERT_SHA256, repo=REPO):
    """Test actual decryptability with fresh randomness; returns no sensitive data.

    Cryptographic possession now is distinct from future custody/availability,
    backup of the Railway Volume, or authenticity of provider data.
    """
    require(os.name == "posix" and hasattr(os, "geteuid"))
    require(OPENSSL.is_file() and os.access(OPENSSL, os.X_OK))
    require(key.is_absolute() and key.name not in (".", "..", ""))
    require(key == key.resolve(strict=True))
    require(not key.is_relative_to(repo) and not repo.is_relative_to(key))
    require(key.parent.is_dir() and key.parent == key.parent.resolve(strict=True))
    info = key.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
    require(info.st_uid == os.geteuid() and not (stat.S_IMODE(info.st_mode) & 0o077))
    require(0 < info.st_size <= 64 * 1024)
    require(cert.is_file() and not cert.is_symlink() and cert == cert.resolve(strict=True))
    require(hmac.compare_digest(hashlib.sha256(cert.read_bytes()).hexdigest(), pinned_digest))

    # The challenge and ciphertext are synthetic; never touch Railway or a
    # real exported NEXUS workspace. A mismatched key must fail cryptographically.
    with tempfile.TemporaryDirectory(prefix="nexus-local-recovery-check-") as temp:
        root = Path(temp)
        plain = root / "challenge"
        encrypted = root / "challenge.cms"
        decoded = root / "decoded"
        plain.write_bytes(os.urandom(48))
        os.chmod(plain, 0o600)
        child_env = {"PATH": "/usr/bin:/bin", "HOME": str(root), "LANG": "C"}
        commands = (
            [str(OPENSSL), "cms", "-encrypt", "-aes-256-gcm", "-binary",
             "-stream", "-in", str(plain), "-outform", "DER",
             "-out", str(encrypted), str(cert)],
            [str(OPENSSL), "cms", "-decrypt", "-inform", "DER",
             "-in", str(encrypted), "-recip", str(cert), "-inkey",
             str(key), "-out", str(decoded)],
        )
        for command in commands:
            try:
                proc = subprocess.run(command, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      env=child_env, timeout=20, check=False)
            except (OSError, subprocess.TimeoutExpired):
                raise KeyCheckBlocked("recovery-key local proof blocked") from None
            require(proc.returncode == 0)
        require(decoded.is_file() and decoded.stat().st_size == 48)
        require(hmac.compare_digest(plain.read_bytes(), decoded.read_bytes()))
    return True


def main():
    p = argparse.ArgumentParser(description="Verify owner-local Stage D RSA recovery-key possession; no provider/network access")
    p.add_argument("--private-key", required=True, type=Path,
                   help="absolute private key path, outside public repo; NEVER paste key content")
    args = p.parse_args()
    # Prevent accidental key placement/execution on a hosted or public runner.
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        print("LOCAL RECOVERY KEY PROOF: BLOCKED (cloud runner prohibited)", file=sys.stderr)
        return 1
    try:
        prove(args.private_key)
    except (ValueError, OSError, RuntimeError):
        print("LOCAL RECOVERY KEY PROOF: BLOCKED (no backup or recovery claim)", file=sys.stderr)
        return 1
    print("LOCAL RECOVERY KEY PROOF: PASS (pinned public certificate decrypts a fresh synthetic challenge)")
    print("No production backup, owner custody, or independent live restore has been proven.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
