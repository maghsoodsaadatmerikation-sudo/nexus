"""Real subprocess/HTTP acceptance of the local Studio launcher; synthetic data only."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import socket
import stat
import subprocess
import sys
import threading
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/run-local-studio.py"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def environment(**changes):
    result = {k: v for k, v in os.environ.items() if not k.startswith("NEXUS_")}
    result.update(changes)
    return result


def command(state, port=0):
    return [sys.executable, str(SCRIPT), "--state-dir", str(state), "--port", str(port)]


@contextmanager
def launch(state, port=0, **changes):
    process = subprocess.Popen(command(state, port), env=environment(**changes),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert select.select([process.stdout], [], [], 15)[0], "startup timed out"
        line = process.stdout.readline()
        assert line, process.stderr.read() if process.poll() is not None else "missing startup result"
        info = json.loads(line)
        assert info["state"] == "ready" and info["authority"] == "none"
        token = (state / "api-token").read_text().strip()
        assert token not in line
        yield info, token
    finally:
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0
        if (state / "api-token").exists():
            assert (state / "api-token").read_text().strip() not in stdout + stderr


def get(url, *, data=None, token=None):
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers,
                                    data=json.dumps(data).encode() if data is not None else None)
    try:
        response = OPENER.open(request, timeout=3)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.read(2 * 1024 * 1024)


def test_local_guide_restart_lock_and_shutdown(tmp_path):
    state = tmp_path / "studio"
    with launch(state, NEXUS_API_TOKEN="unrelated-core-secret",
                NEXUS_CORE_URL="https://private.invalid", NEXUS_STUDIO_TOKEN="ambient-not-used") as (info, token):
        assert info["url"].startswith("http://127.0.0.1:")
        assert info["model_configured"] is False
        assert info["model_availability"] == "not-probed"
        assert len(token) == 64 and token != "ambient-not-used"
        assert stat.S_IMODE(state.stat().st_mode) == 0o700
        assert stat.S_IMODE((state / "api-token").stat().st_mode) == 0o600
        code, html = get(info["url"])
        assert code == 200 and b"NEXUS Studio" in html and token.encode() not in html
        base = info["url"].removesuffix("/studio")
        code, body = get(base + "/")
        assert code == 200 and json.loads(body)["core"] == "unconfigured"
        code, _ = get(base + "/studio-api/respond", data={})
        assert code == 503  # disabled means disabled, never a simulated AI reply
        duplicate = subprocess.run(command(state), env=environment(), capture_output=True, text=True, timeout=5)
        assert duplicate.returncode == 1 and "already in use" in duplicate.stderr
    with pytest.raises(urllib.error.URLError):
        get(base + "/healthz")
    with launch(state) as (_, reused):
        assert reused == token


def test_explicit_synthetic_provider_roundtrip_and_no_startup_contact(tmp_path):
    calls = []
    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append((self.headers.get("authorization"), json.loads(self.rfile.read(int(self.headers["content-length"])))))
            payload = json.dumps({"choices": [{"message": {"content": "SYNTHETIC ACCEPTANCE ONLY"}, "finish_reason": "stop"}]}).encode()
            self.send_response(200)
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with launch(tmp_path / "studio", NEXUS_MODEL_URL=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                    NEXUS_MODEL_ID="synthetic-only", NEXUS_MODEL_API_KEY="synthetic-provider-secret") as (info, token):
            assert info["model_configured"] is True and calls == []
            base = info["url"].removesuffix("/studio")
            _, raw = get(base + "/studio-api/status")
            body = {"configuration_id": json.loads(raw)["configuration_id"], "consent": True,
                    "messages": [{"role": "user", "content": "synthetic acceptance question"}]}
            code, raw = get(base + "/studio-api/respond", data=body)
            assert code == 401 and calls == []
            code, raw = get(base + "/studio-api/respond", data=body, token=token)
            assert code == 200 and json.loads(raw)["text"] == "SYNTHETIC ACCEPTANCE ONLY"
            assert len(calls) == 1 and calls[0][0] == "Bearer synthetic-provider-secret"
            assert token not in json.dumps(calls)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


@pytest.mark.parametrize("changes", [
    {"NEXUS_MODEL_ID": "partial"},
    {"NEXUS_MODEL_URL": "https://private.invalid/secret", "NEXUS_MODEL_ID": "x", "NEXUS_MODEL_ADAPTER": "invalid"},
    {"NEXUS_MODEL_API_KEY": "private-provider-secret"},
    {"NEXUS_MODEL_SECONDARY_ID": "partial-secondary"},
    {"NEXUS_MODEL_URL": "http://127.0.0.1:9999/v1/chat/completions",
     "NEXUS_MODEL_ID": "synthetic", "NEXUS_MODEL_WORKSPACE_ID": "invalid-private-workspace"},
    {"NEXUS_MODEL_URL": "http://127.0.0.1:9999/v1/chat/completions",
     "NEXUS_MODEL_ID": "synthetic", "NEXUS_MODEL_TERTIARY_API_KEY": "private-tertiary-key"},
])
def test_invalid_configuration_fails_before_creating_state(tmp_path, changes):
    state = tmp_path / "studio"
    result = subprocess.run(command(state), env=environment(**changes), capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and "model configuration" in result.stderr
    assert not state.exists() and "private" not in result.stdout + result.stderr


def test_multi_model_streaming_and_durable_budget_roundtrip(tmp_path):
    calls = []

    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["content-length"])))
            calls.append((self.path, self.headers.get("authorization"), payload))
            if payload.get("stream"):
                frames = [
                    {"choices": [{"index": 0, "delta": {"role": "assistant", "content": "Synthetic stream"},
                                  "finish_reason": None}]},
                    {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
                ]
                raw = ("".join("data: " + json.dumps(frame) + "\n\n" for frame in frames)
                       + "data: [DONE]\n\n").encode()
                media = "text/event-stream"
            else:
                raw = json.dumps({"choices": [{"message": {"role": "assistant", "content": "Synthetic secondary"},
                                               "finish_reason": "stop"}]}).encode()
                media = "application/json"
            self.send_response(200)
            self.send_header("content-type", media)
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    state = tmp_path / "studio"
    provider_base = f"http://127.0.0.1:{server.server_port}"
    settings = {
        "NEXUS_MODEL_URL": provider_base + "/primary",
        "NEXUS_MODEL_ID": "synthetic-primary",
        "NEXUS_MODEL_API_KEY": "synthetic-primary-secret",
        "NEXUS_MODEL_STREAMING": "1",
        "NEXUS_MODEL_SECONDARY_URL": provider_base + "/secondary",
        "NEXUS_MODEL_SECONDARY_ID": "synthetic-secondary",
        "NEXUS_MODEL_SECONDARY_API_KEY": "synthetic-secondary-secret",
        "NEXUS_MODEL_TERTIARY_URL": "https://api.anthropic.com/v1/messages",
        "NEXUS_MODEL_TERTIARY_ID": "synthetic-tertiary",
        "NEXUS_MODEL_TERTIARY_ADAPTER": "anthropic",
        "NEXUS_MODEL_TERTIARY_API_KEY": "synthetic-tertiary-secret",
        "NEXUS_MODEL_TERTIARY_WORKSPACE_ID": "wrkspc_0123456789abcdef0123456789abcdef",
        "NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS": "2",
    }
    try:
        with launch(state, **settings) as (info, token):
            base = info["url"].removesuffix("/studio")
            code, raw = get(base + "/studio-api/status")
            assert code == 200 and calls == []
            catalog = {entry["slot"]: entry for entry in json.loads(raw)["models"]}
            assert set(catalog) == {"primary", "secondary", "tertiary"}
            assert catalog["primary"]["streaming"] is True
            assert not catalog["secondary"].get("streaming", False)
            for slot in catalog:
                code, diagnostic = get(base + "/studio-api/operator-readiness?model_slot=" + slot, token=token)
                assert code == 200 and json.loads(diagnostic)["readiness"] == "READY_TO_TEST"
                for secret in ("synthetic-primary-secret", "synthetic-secondary-secret",
                               "synthetic-tertiary-secret", settings["NEXUS_MODEL_TERTIARY_WORKSPACE_ID"], token):
                    assert secret.encode() not in raw + diagnostic
            assert calls == []
            for slot, endpoint in (("primary", "/studio-api/respond-stream"),
                                   ("secondary", "/studio-api/respond")):
                body = {"configuration_id": catalog[slot]["configuration_id"],
                        "model_slot": slot, "consent": True,
                        "messages": [{"role": "user", "content": "Synthetic integration question"}]}
                code, response = get(base + endpoint, data=body, token=token)
                assert code == 200
                if slot == "primary":
                    frames = [json.loads(line) for line in response.splitlines()]
                    assert frames[-1]["type"] == "done"
                    assert frames[-1]["model_slot"] == "primary"
                    assert any(frame.get("text") == "Synthetic stream" for frame in frames)
                else:
                    assert json.loads(response)["text"] == "Synthetic secondary"
                    assert json.loads(response)["model_slot"] == "secondary"
            assert [(path, auth) for path, auth, _ in calls] == [
                ("/primary", "Bearer synthetic-primary-secret"),
                ("/secondary", "Bearer synthetic-secondary-secret"),
            ]
            assert token not in json.dumps(calls)
        with launch(state, **settings) as (info, token):
            base = info["url"].removesuffix("/studio")
            _, diagnostic = get(base + "/studio-api/operator-readiness", token=token)
            readiness = json.loads(diagnostic)
            assert readiness["readiness"] == "LOCAL_BUDGET_EXHAUSTED"
            assert readiness["local_request_budget"]["remaining"] == 0
            assert readiness["operator_next_step"] == "review_persistent_attempt_limit_and_provider_quota"
            code, _ = get(base + "/studio-api/respond", data=body, token=token)
            assert code == 429 and len(calls) == 2
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def test_occupied_port_cannot_be_mistaken_for_our_service(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        result = subprocess.run(command(tmp_path / "studio", listener.getsockname()[1]),
                                env=environment(), capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and "BLOCKED" in result.stderr and result.stdout == ""


def test_insecure_and_symlinked_token_is_not_replaced(tmp_path):
    state = tmp_path / "studio"
    state.mkdir(mode=0o700)
    target = tmp_path / "private-target"
    target.write_text("untouched")
    (state / "api-token").symlink_to(target)
    result = subprocess.run(command(state), env=environment(), capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and target.read_text() == "untouched"
    (state / "api-token").unlink()
    (state / "api-token").write_text("a" * 64 + "\n")
    (state / "api-token").chmod(0o644)
    result = subprocess.run(command(state), env=environment(), capture_output=True, text=True, timeout=5)
    assert result.returncode == 1 and "private regular files" in result.stderr


def test_server_retains_lock_when_supervisor_is_killed(tmp_path):
    import signal
    state = tmp_path / "studio"
    process = subprocess.Popen(command(state), env=environment(), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    child_handle = None
    try:
        assert select.select([process.stdout], [], [], 15)[0]
        info = json.loads(process.stdout.readline())
        child_handle = os.pidfd_open(info["gateway_pid"])
        process.kill()
        process.communicate(timeout=5)
        duplicate = subprocess.run(command(state), env=environment(), capture_output=True, text=True, timeout=5)
        assert duplicate.returncode == 1 and "already in use" in duplicate.stderr
        signal.pidfd_send_signal(child_handle, signal.SIGTERM)
        assert select.select([child_handle], [], [], 10)[0], "orphan server did not stop"
        with launch(state) as (restarted, _):
            assert restarted["state"] == "ready"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
        if child_handle is not None:
            try:
                signal.pidfd_send_signal(child_handle, signal.SIGKILL)
            except ProcessLookupError:
                pass
            os.close(child_handle)


def test_same_port_restart_preserves_local_identity(tmp_path):
    state = tmp_path / "studio"
    with launch(state) as (first, first_token):
        port = int(first["url"].removesuffix("/studio").rsplit(":", 1)[1])
        assert get(first["url"])[0] == 200
    with launch(state, port=port) as (second, second_token):
        assert second["url"] == first["url"]
        assert second_token == first_token
        assert get(second["url"])[0] == 200
