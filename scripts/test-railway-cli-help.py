#!/usr/bin/env python3
"""Verify the real pinned Railway CLI's help grammar without auth/network calls.

This program imports only the local NEXUS capture command constructor.
The subprocesses it invokes are all --version or --help.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--railway-bin",required=True,type=Path)
    args=p.parse_args()
    if any(os.environ.get(k) for k in
           ("RAILWAY_TOKEN","RAILWAY_API_TOKEN","RENDER_API_KEY","NEXUS_API_TOKEN")):
        raise SystemExit("BLOCKED: provider or NEXUS credential present")
    capture=Path(__file__).with_name("capture-railway-volume-readonly.py")
    spec=importlib.util.spec_from_file_location("nexus_readonly_volume_cli",capture)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cli=args.railway_bin
    if not cli.is_absolute() or not cli.is_file() or cli.is_symlink():
        raise SystemExit("BLOCKED: exact private CLI binary missing")
    try:
        module.validate_railway_cli(cli)
    except (module.CaptureBlocked,OSError,ValueError) as exc:
        reason = str(exc) if isinstance(exc,module.CaptureBlocked) else type(exc).__name__
        raise SystemExit("BLOCKED: "+reason) from None

    cmd=module.permitted_download_command(cli,
        Path("/private/nexus-export/copied-data"))
    assert cmd[1:]==[
        "--project",module.PROJECT,
        "--environment",module.ENVIRONMENT,
        "--service",module.SERVICE,
        "volume","files","--volume",module.VOLUME,
        "download","/","/private/nexus-export/copied-data",
        "--concurrency","1"
    ]
    assert not any(x in cmd for x in
        ("upload","delete","detach","attach","restore","redeploy",
         "restart","--overwrite","--override"))
    print("PASS: real, pinned Railway CLI supports exact NEXUS read-only download help grammar")
    print("SCOPE: no login, no file listing, no remote GET, no backups and no production mutation")


if __name__=="__main__":
    main()
