#!/usr/bin/env python3
"""Supervise a loopback-only Studio with private, reusable gateway credentials.

Run with: uv run --project nexus-cloud --frozen python scripts/run-local-studio.py
This launches the optional Studio adapter, not the Rust constitutional gateway.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def pilot_helpers():
    spec = importlib.util.spec_from_file_location("local_pilot", ROOT / "scripts/run-local-pilot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path,
                        default=Path.home() / ".local/share/nexus-local-studio")
    parser.add_argument("--port", type=int, default=8000,
                        help="loopback port, or 0 to select a free port")
    args = parser.parse_args()
    if args.port != 0 and not 1024 <= args.port <= 65535:
        parser.error("port must be 0 or between 1024 and 65535")
    process = None
    lock_fd = None
    listener = None
    stopped = False

    def stop(signum, frame):
        nonlocal stopped
        stopped = True
        if process is not None and process.poll() is None:
            process.terminate()

    try:
        # Validate dependencies and provider configuration before creating state.
        sys.path.insert(0, str(ROOT / "nexus-cloud"))
        import uvicorn  # noqa: F401 -- validates the selected Python environment
        import studio_model
        if not (ROOT / "web/studio.html").is_file():
            raise ValueError("Studio HTML is missing; use a complete repository checkout")
        provider_names = ("NEXUS_MODEL_URL", "NEXUS_MODEL_ID", "NEXUS_MODEL_API_KEY", "NEXUS_MODEL_ADAPTER")
        provider_env = {name: os.environ[name] for name in provider_names if name in os.environ}
        # A saved operator credential, not an ambient Studio token, is used below.
        previous = os.environ.get("NEXUS_STUDIO_TOKEN")
        try:
            os.environ["NEXUS_STUDIO_TOKEN"] = "x" * 64
            configured = studio_model.config() is not None
        finally:
            if previous is None:
                os.environ.pop("NEXUS_STUDIO_TOKEN", None)
            else:
                os.environ["NEXUS_STUDIO_TOKEN"] = previous
        if any(provider_env.values()) and not configured:
            raise ValueError("incomplete or invalid model configuration; review NEXUS_MODEL settings")
        helpers = pilot_helpers()
        state = args.state_dir.absolute()
        helpers.private_directory(state)
        lock_fd = os.open(state / "operator.lock",
                          os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        helpers.check_private_file(lock_fd)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("this Studio state is already in use") from None
        token_path = state / "api-token"
        token = helpers.stored_token(token_path)
        # Reserve the exact socket before spawning: no port-selection/probe race.
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", args.port))
        listener.listen(128)
        port = listener.getsockname()[1]
        base = "http://127.0.0.1:" + str(port)
        # Do not inherit core authority tokens, proxy settings, Python injection,
        # external CORS origins or unrelated service credentials into this child.
        env = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONNOUSERSITE": "1",
               "PYTHONDONTWRITEBYTECODE": "1", "NEXUS_STUDIO_TOKEN": token, **provider_env}
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--app-dir", str(ROOT / "nexus-cloud"),
             "--fd", str(listener.fileno()), "--no-access-log", "--log-level", "error"],
            env=env, cwd=ROOT, pass_fds=(listener.fileno(), lock_fd),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # Only the child retains the listening socket and operator lock copy.
        listener.close()
        listener = None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 10
        while not stopped and time.monotonic() < deadline:
            if process.poll() is not None:
                raise ValueError("Studio exited before startup completed")
            try:
                with opener.open(base + "/healthz", timeout=.5) as response:
                    health = json.loads(response.read(4096))
                with opener.open(base + "/studio-api/status", timeout=.5) as response:
                    model = json.loads(response.read(8192))
                if (health != {"status": "ok", "scope": "transport-liveness-only"}
                        or model.get("configured") is not configured or model.get("authority") != "none"):
                    raise ValueError("Studio startup probe returned unexpected metadata")
                if process.poll() is not None:
                    raise ValueError("Studio exited during startup")
                print(json.dumps({"url": base + "/studio", "gateway_pid": process.pid,
                    "state": "ready", "model_configured": configured,
                    "model_availability": "not-probed", "token_file": str(token_path),
                    "authority": "none"}), flush=True)
                # Poll so a stop request reaches bounded cleanup even if the
                # child ignores SIGTERM; an unbounded wait would never unwind.
                while not stopped:
                    try:
                        code = process.wait(timeout=.2)
                        return 0 if stopped else code if code > 0 else 1
                    except subprocess.TimeoutExpired:
                        continue
                return 0
            except (OSError, json.JSONDecodeError):
                time.sleep(.05)
        if stopped:
            return 0
        raise ValueError("Studio startup timed out")
    except ImportError:
        print("NEXUS LOCAL STUDIO: BLOCKED (run with uv run --project nexus-cloud --frozen python)", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print("NEXUS LOCAL STUDIO: BLOCKED (" + message + ")", file=sys.stderr)
        return 1
    finally:
        if listener is not None:
            listener.close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if lock_fd is not None:
            os.close(lock_fd)


if __name__ == "__main__":
    raise SystemExit(main())
