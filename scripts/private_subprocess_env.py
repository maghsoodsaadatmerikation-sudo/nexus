#!/usr/bin/env python3
"""Minimal environment for private Stage D subprocesses.

Never forward the operator's entire environment to a CLI parser, private
snapshot intake or operator-supplied Rust validator. This reduces *ambient*
secret exposure; it is NOT an OS sandbox or a trusted-executable attestation.
"""
import os
from pathlib import Path

RAILWAY_CREDENTIAL_KEYS = ("RAILWAY_TOKEN", "RAILWAY_API_TOKEN")


def child_env(*, railway_download=False, private_home=None):
    """Explicit allowlist; Railway credentials exist ONLY in download mode."""
    home = str(private_home) if private_home is not None else os.environ.get("HOME", "/tmp")
    env = {
        "HOME": home,
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "CI": "true",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "RAILWAY_NO_AUTO_UPDATE": "1",
    }
    if railway_download:
        for name in RAILWAY_CREDENTIAL_KEYS:
            token = os.environ.get(name)
            if token:
                env[name] = token
    return env
