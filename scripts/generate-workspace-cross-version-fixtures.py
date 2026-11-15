#!/usr/bin/env python3
"""Generate entirely synthetic, semantically checked core reader test cases.

Case names contain no user data. These snapshots are never imported, never
sent to a model, and are deleted with the ephemeral GitHub Actions runner.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys


def base():
    return {
        "schema_version": 1,
        "workspace": {
            "id": "w",
            "question": "Disposable synthetic question",
            "goal": None, "constraints": [], "values": [],
            "claims": [], "alternatives": [], "judgment": None,
        },
        "events": [{
            "sequence": 0,
            "provenance_id": "human:creator",
            "kind": "WorkspaceCreated",
        }],
    }


def claim(x):
    x["workspace"]["claims"].append({
        "id": "c1", "text": "Disposable claim", "origin": "Human",
        "uncertainty": "Unknown",
    })
    x["events"].append({
        "sequence": 1, "provenance_id": "human:claim",
        "kind": {"ClaimAdded": {"claim_id": "c1"}},
    })


def generate(dest):
    dest.mkdir(parents=True, exist_ok=False)
    positive = {}
    negative = {}
    positive["creation"] = base()
    positive["claim"] = deepcopy(positive["creation"])
    claim(positive["claim"])
    negative["schema-v2"] = deepcopy(positive["creation"])
    negative["schema-v2"]["schema_version"] = 2
    negative["missing-creation"] = deepcopy(positive["creation"])
    negative["missing-creation"]["events"] = []
    negative["wrong-audit-sequence"] = deepcopy(positive["claim"])
    negative["wrong-audit-sequence"]["events"][1]["sequence"] = 3
    negative["unknown-event-kind"] = deepcopy(positive["claim"])
    negative["unknown-event-kind"]["events"][1]["kind"] = {"UnreviewedEvent": {}}
    negative["unknown-workspace-field"] = deepcopy(positive["creation"])
    negative["unknown-workspace-field"]["workspace"]["undocumented"] = "do-not-drop"
    negative["unknown-snapshot-field"] = deepcopy(positive["creation"])
    negative["unknown-snapshot-field"]["authority"] = "claimed"
    negative["unknown-event-field"] = deepcopy(positive["claim"])
    negative["unknown-event-field"]["events"][1]["unreviewed"] = True
    negative["identity-mismatch"] = deepcopy(positive["creation"])
    negative["identity-mismatch"]["workspace"]["id"] = "other"
    negative["empty-provenance"] = deepcopy(positive["claim"])
    negative["empty-provenance"]["events"][1]["provenance_id"] = ""
    for category, values in (("valid", positive), ("invalid", negative)):
        for name, value in values.items():
            raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")
            (dest / f"{category}-{name}.json").write_bytes(raw)
    return len(positive), len(negative)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("expected one empty, isolated fixture directory path")
    positive, negative = generate(Path(sys.argv[1]))
    print(json.dumps({
        "status": "GENERATED_SYNTHETIC_ONLY",
        "accepted_cases": positive,
        "rejected_cases": negative,
        "sensitive_data_used": False,
    }))


if __name__ == "__main__":
    main()
