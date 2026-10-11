#!/usr/bin/env python3
"""Synthetic full-data recovery checks over a live HTTP listener."""
import argparse
import json
import os
from pathlib import Path
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("request_id")
    parser.add_argument("workspace_snapshot", type=Path)
    parser.add_argument("--repeat", action="store_true")
    parser.add_argument("--quarantined", action="store_true")
    args = parser.parse_args()
    token = os.environ["NEXUS_API_TOKEN"]

    def call(method, path, body=None, authenticated=True):
        headers = {"content-type": "application/json"}
        if authenticated:
            headers["authorization"] = "Bearer " + token
        request = urllib.request.Request(
            args.base_url.rstrip("/") + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers, method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def submit(request_id):
        return call("POST", "/v1/requests", {
            "request_id": request_id, "authority": "user", "action": "present",
            "value": "synthetic-recovery", "payload": "opaque",
        })

    # Public, non-cached probes must distinguish liveness from write quarantine.
    for path, code, status in [
        ("/livez", 200, "alive"),
        ("/readyz", 503 if args.quarantined else 200,
         "quarantined" if args.quarantined else "ready"),
    ]:
        request = urllib.request.Request(args.base_url.rstrip("/") + path)
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            assert response.status == code
            assert response.headers["Cache-Control"] == "no-store"
            assert json.load(response) == {"status": status}
    print("GATEWAY READINESS: " + ("QUARANTINED" if args.quarantined else "READY") + " PASS")

    expected_workspace = json.loads(args.workspace_snapshot.read_text())
    assert call("GET", "/v1/workspaces/ci-smoke") == (200, expected_workspace)
    for request_id, status in [(args.request_id, "pending"), ("ci-uncertain", "indeterminate")]:
        assert call("GET", "/v1/requests/" + request_id) == (
            200, {"request_id": request_id, "status": status})
        assert submit(request_id)[0] == (503 if args.quarantined else 409)
        assert call("GET", "/v1/requests/" + request_id, authenticated=False)[0] == 401
    if args.quarantined:
        for path in ["/v1/requests", "/v1/workspaces", "/v1/workspaces/import",
                     "/v1/workspaces/ci-smoke/claims", "/v1/workspaces/ci-smoke/alternatives",
                     "/v1/workspaces/ci-smoke/analysis", "/v1/workspaces/ci-smoke/judgment"]:
            assert call("POST", path, {"invalid": True}) == (
                503, {"error": "recovery_acknowledgment_required"})
            assert call("POST", path, {"invalid": True}, authenticated=False)[0] == 401
        assert submit(args.request_id + "-after-restore")[0] == 503
        assert call("GET", "/v1/requests/" + args.request_id + "-after-restore")[0] == 404
        print("FULL DATA RECOVERY QUARANTINE: PASS")
        return
    new_id = args.request_id + "-after-restore"
    assert submit(new_id)[0] == (409 if args.repeat else 202)
    assert call("GET", "/v1/requests/" + new_id) == (
        200, {"request_id": new_id, "status": "pending"})
    assert call("POST", "/v1/workspaces", {
        "workspace_id": "ci-after-volume", "question": "restored data remains writable",
        "provenance_id": "ci:recovery",
    })[0] == (409 if args.repeat else 201)
    assert call("GET", "/v1/workspaces/ci-after-volume")[0] == 200
    print("FULL DATA HTTP RECOVERY" + (" RESTART" if args.repeat else "") + ": PASS")


if __name__ == "__main__":
    main()
