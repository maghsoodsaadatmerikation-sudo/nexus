#!/usr/bin/env python3
"""Fail-closed, dependency-free validator for the single-service Render Blueprint.

Only the reviewed minimal Stage D Blueprint dialect is accepted. This is a
configuration assertion, not an assertion about any live Render service.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FIELDS = {
    "type": "web",
    "name": "nexus-durable-stage-d",
    "runtime": "docker",
    "plan": "0.5c-512mb",
    "region": "frankfurt",
    "dockerfilePath": "./Dockerfile",
    "autoDeployTrigger": "off",
    "healthCheckPath": "/readyz",
    "numInstances": "1",
    "maxShutdownDelaySeconds": "30",
}
EXPECTED_ENV = {
    "NEXUS_API_TOKEN": {"sync": "false"},
    "NEXUS_DATA_DIR": {"value": "/data"},
    "NEXUS_BIND_ADDR": {"value": "0.0.0.0:3000"},
    "PORT": {"value": "3000"},
}
EXPECTED_DISK = {"name": "nexus-data", "mountPath": "/data", "sizeGB": "1"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def scalar(value: str) -> str:
    """Admit plain scalars and one exact pair of simple quotes, not YAML tags."""
    require(bool(value) and value == value.strip(), "empty or padded scalar")
    require(not re.search(r"[\x00-\x1f#{}\[\]&*!|>]", value),
            "unreviewed YAML scalar syntax")
    if value[0] in ("'", '"'):
        require(len(value) >= 2 and value[-1] == value[0],
                "unbalanced quoted scalar")
        value = value[1:-1]
        require(value and not any(c in value for c in "'\"\\"),
                "unsupported escape in scalar")
    else:
        require(not any(c in value for c in "'\""),
                "unsupported quote in plain scalar")
    return value


def verify(source: str) -> None:
    require(len(source.encode("utf-8")) <= 32 * 1024,
            "Blueprint exceeds static validation limit")
    require("\t" not in source and "\r" not in source,
            "tabs and CR are not accepted in the Blueprint")
    fields: dict[str, str] = {}
    env: dict[str, dict[str, str]] = {}
    disk: dict[str, str] = {}
    state = "root"
    service_count = 0
    current_env = None

    for line_number, raw in enumerate(source.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        # No inline comments, aliases, anchors, YAML merge, or additional
        # top-level objects. Unexpected syntax is rejected, never ignored.
        require(not raw.endswith(" ") and not raw.startswith("\ufeff"),
                f"line {line_number}: unexpected whitespace or BOM")
        if raw == "services:":
            require(state == "root", "duplicate or out-of-order services root")
            state = "services"
            continue
        if raw == "  - type: web":
            require(state == "services" and service_count == 0,
                    "Blueprint must declare exactly one service")
            service_count += 1
            fields["type"] = "web"
            state = "service"
            continue

        match = re.fullmatch(r"    ([A-Za-z][A-Za-z0-9]*):(?: (.+))?", raw)
        if match:
            require(service_count == 1, "unexpected service entry")
            key, raw_value = match.groups()
            require(key not in fields, f"duplicate service key: {key}")
            require(key in EXPECTED_FIELDS or key in ("envVars", "disk"),
                    f"unreviewed service setting: {key}")
            if key in ("envVars", "disk"):
                require(raw_value is None, f"{key} must be a mapping")
                state = "env" if key == "envVars" else "disk"
                fields[key] = "<mapping>"
                current_env = None
            else:
                require(raw_value is not None, f"missing scalar: {key}")
                fields[key] = scalar(raw_value)
                state = "service"
            continue

        match = re.fullmatch(r"      - key: ([A-Z][A-Z0-9_]*)", raw)
        if match:
            require(state == "env", "unexpected environment entry")
            current_env = match.group(1)
            require(current_env not in env, f"duplicate environment key: {current_env}")
            env[current_env] = {}
            continue

        match = re.fullmatch(r"        ([A-Za-z][A-Za-z0-9]*): (.+)", raw)
        if match:
            require(state == "env" and current_env is not None,
                    "orphaned environment setting")
            key, value = match.groups()
            require(key not in env[current_env],
                    f"duplicate environment field: {current_env}.{key}")
            env[current_env][key] = scalar(value)
            continue

        match = re.fullmatch(r"      ([A-Za-z][A-Za-z0-9]*): (.+)", raw)
        if match:
            require(state == "disk", "unexpected nested setting")
            key, value = match.groups()
            require(key not in disk, f"duplicate disk setting: {key}")
            disk[key] = scalar(value)
            continue
        raise ValueError(f"line {line_number}: unsupported Blueprint structure")

    require(service_count == 1, "missing or multiple services")
    expected_fields = dict(EXPECTED_FIELDS, envVars="<mapping>", disk="<mapping>")
    require(fields == expected_fields,
            f"service profile or manual-deploy boundary changed: {fields!r}")
    require(env == EXPECTED_ENV, "environment settings or secret handling changed")
    require(disk == EXPECTED_DISK, "persistent disk contract changed")


def main() -> None:
    require(len(sys.argv) <= 2, "expected at most one Blueprint path")
    path = Path(sys.argv[1]) if len(sys.argv) == 2 else ROOT / "render.yaml"
    verify(path.read_text(encoding="utf-8"))
    print("RENDER MANUAL DEPLOY CONFIG BOUNDARY: PASS")
    print("PROVIDER LIVE SETTINGS: NOT VERIFIED")
    print("STAGE D PRODUCTION RECOVERY: NOT VERIFIED")


if __name__ == "__main__":
    try:
        main()
    except (OSError, UnicodeError, ValueError) as error:
        print(f"RENDER MANUAL DEPLOY CONFIG BOUNDARY: FAIL ({error})",
              file=sys.stderr)
        raise SystemExit(1)
