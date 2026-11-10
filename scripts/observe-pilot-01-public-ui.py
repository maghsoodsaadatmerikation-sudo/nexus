#!/usr/bin/env python3
"""Read-only public NEXUS UI observation. No auth token or POST, no promotion."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

LIMIT = 128 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def inspect_page(body, pinned, current):
    if len(body) > LIMIT:
        return "BODY_OVERSIZE"
    if (b"<title>NEXUS" not in body or b'id="token"' not in body or
            b'id="createWorkspaceButton"' not in body or
            b'id="recordJudgmentButton"' not in body or
            b'id="backupWorkspaceButton"' not in body):
        return "UNRECOGNIZED_UI"
    if body != pinned:
        return "PINNED_UI_MISMATCH"
    return "CURRENT_MAIN_UI" if body == current else "OLDER_PINNED_UI"


def fetch_page(origin, timeout=20):
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request(origin.rstrip("/") + "/", method="GET",
                                     headers={"Cache-Control": "no-cache"})
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as err:
        response = err
    with response:
        code = response.status
        if code != 200:
            return code, None
        body = response.read(LIMIT + 1)
        return code, body


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--origin", required=True)
    p.add_argument("--deployed-commit", required=True)
    args = p.parse_args()
    u = urllib.parse.urlsplit(args.origin)
    if (u.scheme != "https" or not u.hostname or u.username or u.password or
            u.query or u.fragment or u.path not in ("", "/")):
        p.error("only a credential-free HTTPS origin is allowed")
    if not re.fullmatch(r"[a-f0-9]{40}", args.deployed_commit):
        p.error("expected deployed commit must be an immutable SHA")
    # The reference is tracked Git content, not an untrusted site assertion.
    try:
        pinned = subprocess.run(["git", "show", args.deployed_commit + ":web/index.html"],
                                capture_output=True, check=True, timeout=10).stdout
        current = Path("web/index.html").read_bytes()
    except (subprocess.CalledProcessError, FileNotFoundError, TimeoutError):
        p.error("local pinned HTML reference could not be established")
    code, body, classification = 0, None, "NETWORK_ERROR"
    try:
        code, body = fetch_page(args.origin)
        classification = inspect_page(body, pinned, current) if body is not None else "HTTP_NOT_200"
    except (OSError, TimeoutError, urllib.error.URLError):
        pass
    report = {
        "schema": "nexus.pilot-01.public-ui-observation.v1",
        "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "public_origin": args.origin.rstrip("/"),
        "http_status": code,
        "pinned_deployed_commit": args.deployed_commit,
        "pinned_html_sha256": hashlib.sha256(pinned).hexdigest(),
        "current_main_html_sha256": hashlib.sha256(current).hexdigest(),
        "observed_html_sha256": hashlib.sha256(body).hexdigest() if body is not None else None,
        "ui_revision_classification": classification,
        "status": "PASS_STATIC_OBSERVATION" if classification in
                  ("CURRENT_MAIN_UI", "OLDER_PINNED_UI") else "BLOCKED",
        "authenticated_session": "NOT_TESTED",
        "workspace_writes": "NOT_PERFORMED",
        "backup_and_recovery": "NOT_VERIFIED",
        "promotion_ready": False,
        "production_mutation": False,
        "authority": "none",
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS_STATIC_OBSERVATION" else 2


if __name__ == "__main__":
    raise SystemExit(main())
