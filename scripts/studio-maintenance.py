#!/usr/bin/env python3
"""Audit and optionally repair generated Studio assets from a clean commit."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
BUILDERS = ("build-studio.py", "build-device-model.py", "build-studio-static.py")
GENERATED = {
    "web/studio.html",
    "public/studio/index.html",
    "public/studio/manifest.json",
    "public/studio/service-worker.js",
    "public/studio/studio-orchestra.js",
    "public/studio/studio-core.js",
    "public/studio/icons/nexus-192.png",
    "public/studio/icons/nexus-512.png",
    *{
        f"public/studio/device/{name}" for name in (
            "device-engine.js", "device-ui.js", "device-worker.js", "model-manifest.json",
            "vendor/LICENSE-jinja.txt", "vendor/LICENSE-onnxruntime.txt",
            "vendor/LICENSE-transformers.txt", "vendor/ort-wasm-simd-threaded.asyncify.mjs",
        )
    },
}


def run(cwd, *args, patch=None):
    # Keep the builders' assertions enabled and their bytecode out of the patch.
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("PYTHONOPTIMIZE", None)
    result = subprocess.run(args, cwd=cwd, input=patch, capture_output=True, timeout=60, env=env)
    if result.returncode:
        message = (result.stderr or result.stdout).decode(errors="replace").strip()
        raise RuntimeError(f"{' '.join(args)} failed: {message[-1600:]}")
    return result.stdout


def git(cwd, *args, patch=None):
    return run(cwd, "git", *args, patch=patch)


def current_changes(cwd):
    return git(cwd, "status", "--porcelain=v1", "-z", "--untracked-files=all")


def require_base(base):
    if current_changes(ROOT) or git(ROOT, "rev-parse", "HEAD").decode().strip() != base:
        raise RuntimeError("selected checkout must remain clean and at the audited commit")


def require_generated_paths(checkout):
    for path in GENERATED:
        target = checkout / path
        if target.is_symlink() or not target.resolve().is_relative_to(checkout):
            raise RuntimeError(f"generated path escapes its checkout: {path}")


def inspect(base):
    with TemporaryDirectory(prefix="nexus-studio-maintenance-") as tmp:
        checkout = Path(tmp) / "checkout"
        git(ROOT, "worktree", "add", "--quiet", "--detach", str(checkout), base)
        try:
            require_generated_paths(checkout.resolve())
            for builder in BUILDERS:
                run(checkout, sys.executable, f"scripts/{builder}")
            # The static check also verifies the standalone and device packages.
            run(checkout, sys.executable, "scripts/build-studio-static.py", "--check")
            # Scope-check the exact bytes that will enter the patch, including
            # any side effects from verification.
            require_generated_paths(checkout.resolve())
            changed = []
            missing = []
            for entry in current_changes(checkout).decode().split("\0"):
                if not entry:
                    continue
                path = entry[3:]
                kind = entry[:3]
                if kind not in {" M ", "?? "} or path not in GENERATED:
                    raise RuntimeError(f"unexpected builder change: {entry}")
                changed.append(path)
                if kind == "?? ":
                    missing.append(path)
            if missing:
                git(checkout, "add", "--intent-to-add", "--", *missing)
            patch = git(checkout, "diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", "HEAD")
            return sorted(changed), patch
        finally:
            git(ROOT, "worktree", "remove", "--force", str(checkout))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair", action="store_true", help="apply the verified generated diff")
    args = parser.parse_args()
    try:
        base = git(ROOT, "rev-parse", "HEAD").decode().strip()
        require_base(base)
        changed, patch = inspect(base)
        status = "drift" if changed else "healthy"
        if args.repair and changed:
            require_base(base)
            git(ROOT, "apply", "--check", "-", patch=patch)
            git(ROOT, "apply", "-", patch=patch)
            status = "repaired"
        print(json.dumps({"status": status, "base_commit": base, "changed_files": changed}))
        return int(status == "drift")
    except (RuntimeError, OSError, subprocess.TimeoutExpired, UnicodeError) as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
