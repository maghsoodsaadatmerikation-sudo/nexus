"""Private, unprivileged Unix-socket control plane for NEXUS operator-only plans.

No HTTP, TCP, browser, automatic model action, Docker socket API, or remote
credential handling. The local human prepares a v3 plan and independently
supplies its canonical SHA-256. The daemon verifies both before queueing work.
A stop signal is cooperative; cancellation is not a filesystem rollback.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import socket
import socketserver
import stat
import struct
import threading
from pathlib import Path

from agent_chat_handoff import REVIEW_SCHEMA, chat_receipt, private_export_dir, read_operator_file
from agent_journal import ApprovalJournal
from agent_workspace import Workspace, WorkspaceDenied, WORKSPACE_ID
from engineering_agent import HASH, execute_plan, parse_plan

MAX_REQUEST_BYTES = 16_384
MAX_RESPONSE_BYTES = 16_384
MAX_ACTIVE_CLIENTS = 12
SOCKET_NAME = ".nexus-operator.sock"
TOKEN_NAME = ".nexus-operator.token"


def _root(root: str | Path) -> Path:
    """Reject root aliases through ancestor symlinks before using a pathname.

    This is a filesystem preflight, not hostile same-UID mount isolation.
    The operator must also protect the containing parent directories.
    """
    path = Path(root)
    if not path.is_absolute() or ".." in path.parts:
        raise WorkspaceDenied("operator-root-not-private")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise WorkspaceDenied("operator-root-not-private")
    except BaseException:
        os.close(fd)
        raise
    os.close(fd)
    return path


def _regular_private(fd: int, *, max_size: int) -> None:
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1 or st.st_mode & 0o077 or st.st_size > max_size:
        raise WorkspaceDenied("operator-credential-file-unsafe")


def _token_file(root: Path, *, create: bool = False) -> str:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    dfd = os.open(root, flags)
    try:
        if create:
            fd = os.open(TOKEN_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=dfd)
            try:
                secret = os.urandom(32).hex()
                os.write(fd, secret.encode("ascii"))
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(dfd)
            return secret
        fd = os.open(TOKEN_NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=dfd)
        try:
            _regular_private(fd, max_size=64)
            value = os.read(fd, 65).decode("ascii")
            if len(value) != 64 or not re.fullmatch("[0-9a-f]{64}", value):
                raise WorkspaceDenied("operator-token-corrupt")
            return value
        finally:
            os.close(fd)
    finally:
        os.close(dfd)


class OperatorServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False
    request_queue_size = 8

    def __init__(self, root: str | Path):
        if os.name != "posix" or not hasattr(socket, "SO_PEERCRED") or os.getuid() == 0:
            raise WorkspaceDenied("operator-service-needs-unprivileged-linux")
        self.root = _root(root)
        self._state_lock = threading.Lock()
        self._clients = threading.BoundedSemaphore(MAX_ACTIVE_CLIENTS)
        self._running: dict[str, tuple[str, threading.Event]] = {}
        self._token = _token_file(self.root, create=True)
        self._socket = self.root / SOCKET_NAME
        try:
            # The private directory prevents client access before chmod below.
            super().__init__(str(self._socket), OperatorHandler)
            os.chmod(self._socket, 0o600)
            st = self._socket.lstat()
            if not stat.S_ISSOCK(st.st_mode) or st.st_uid != os.getuid():
                raise WorkspaceDenied("unsafe-operator-socket")
        except BaseException:
            self._socket.unlink(missing_ok=True)
            (self.root / TOKEN_NAME).unlink(missing_ok=True)
            raise

    def process_request(self, request, client_address):
        # A connected but silent local client must not spawn an unbounded
        # collection of 5-second handler threads. Refuse excess immediately.
        if not self._clients.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._clients.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._clients.release()

    def server_close(self):
        # Closing a service while work is running would abandon a live Docker
        # subprocess. Its cancel flag is set and workers get a bounded join.
        with self._state_lock:
            for _, event in self._running.values():
                event.set()
        try:
            super().server_close()
        finally:
            self._socket.unlink(missing_ok=True)
            (self.root / TOKEN_NAME).unlink(missing_ok=True)

    def _run(self, ws: Workspace, plan: dict, digest: str, event: threading.Event) -> None:
        try:
            execute_plan(ws, plan, digest, approved_digest=digest, cancel_event=event)
        except Exception:
            # No false PASS; the single-use journal is retained as started
            # if execution or durable finalization fails.
            pass
        finally:
            with self._state_lock:
                if self._running.get(ws.name, (None, None))[0] == digest:
                    del self._running[ws.name]

    def dispatch(self, value: object, peer_uid: int) -> dict:
        if peer_uid != os.getuid() or not isinstance(value, dict) or set(value) not in (
            {"action", "token", "workspace", "digest"},
            {"action", "token", "workspace", "digest", "plan_path"},
        ):
            return {"status": "denied"}
        token = value.get("token")
        if not isinstance(token, str) or not hmac.compare_digest(token, self._token):
            return {"status": "denied"}
        name, digest, action = value["workspace"], value["digest"], value["action"]
        if not isinstance(name, str) or not WORKSPACE_ID.fullmatch(name) or not isinstance(digest, str) or not HASH.fullmatch(digest):
            return {"status": "denied"}
        has_plan = "plan_path" in value
        if action in ("review", "start"):
            if not has_plan:
                return {"status": "denied"}
            plan_path = value["plan_path"]
            if not isinstance(plan_path, str) or len(plan_path) > 1024:
                return {"status": "denied"}
            try:
                path = Path(plan_path)
                if (not path.is_absolute() or path.name != f"nexus-plan-{digest[:16]}.json"
                        or path.is_symlink()):
                    return {"status": "denied"}
                candidate, observed = parse_plan(read_operator_file(path, require_private=True))
                if observed != digest or candidate["workspace"] != name or candidate["version"] != 3:
                    return {"status": "denied"}
                # Review must not manufacture a workspace merely because an
                # untrusted request supplied a syntactically valid name.
                if not (self.root / name).exists():
                    return {"status": "denied"}
                ws = Workspace(self.root, name)
                private_export_dir(path.parent, ws)
                # The operation lock makes admission consistent with official
                # workspace tools. The worker always checks the hash again
                # before claiming the one-use approval: external writers can
                # still race in an untrusted host-account environment.
                with ws.operation_lock():
                    current = ws.manifest()["sha256"]
                    if current != candidate["expected_workspace_sha256"]:
                        return {"status": "stale-plan-reapproval-required", "authority": "none"}
                    try:
                        ApprovalJournal(ws).read(digest)
                    except FileNotFoundError:
                        pass
                    except (OSError, WorkspaceDenied):
                        return {"status": "unverifiable"}
                    else:
                        return {"status": "already-consumed"}
                with self._state_lock:
                    if name in self._running:
                        return {"status": "busy"}
                    if action == "review":
                        # Deliberately no plan text, filenames, argv, source
                        # content, network results or capability token.
                        steps = [{"index": i, "tool": item["tool"],
                                  "risk": ("executes-container" if item["tool"] == "run" else
                                           "network-metadata" if item["tool"] == "research" else
                                           "writes-files" if item["tool"] in ("write", "edit") else
                                           "exports-archive" if item["tool"] == "package" else
                                           "read-only")}
                                 for i, item in enumerate(candidate["steps"])]
                        review = {"schema": REVIEW_SCHEMA, "authority": "none",
                                  "plan_sha256": digest, "workspace_sha256": current,
                                  "workspace": name, "plan_version": 3,
                                  "steps": steps, "status": "not-executed",
                                  "review_required": True,
                                  "note": "Local operator preflight of reviewed v3 plan. Metadata only; no command executed or approved. Inspect the complete private plan before separately supplying the exact digest."}
                        # Transport status stays outside the strict Studio
                        # summary; the browser cannot promote it to approval.
                        return {"status": "review", "summary": review}
                    event = threading.Event()
                    worker = threading.Thread(target=self._run, args=(ws, candidate, digest, event), daemon=False)
                    self._running[name] = (digest, event)
                    try:
                        worker.start()
                    except BaseException:
                        del self._running[name]
                        raise
                return {"status": "submitted-not-verified", "plan_sha256": digest, "authority": "operator-only"}
            except (OSError, WorkspaceDenied, UnicodeError, ValueError, RuntimeError):
                return {"status": "denied"}
        if has_plan or action not in ("status", "stop"):
            return {"status": "denied"}
        if action == "stop":
            with self._state_lock:
                target = self._running.get(name)
                if not target or target[0] != digest:
                    return {"status": "not-active"}
                target[1].set()
            return {"status": "stop-requested-not-confirmed", "plan_sha256": digest, "authority": "operator-only"}
        try:
            ws = Workspace(self.root, name)
            record = ApprovalJournal(ws).read(digest)
            return {"status": "receipt", **chat_receipt(record)}
        except FileNotFoundError:
            with self._state_lock:
                target = self._running.get(name)
            return {"status": "queued-not-verified" if target and target[0] == digest else "not-found",
                    "plan_sha256": digest, "authority": "none"}
        except (OSError, WorkspaceDenied, ValueError):
            return {"status": "unverifiable", "plan_sha256": digest, "authority": "none"}


class OperatorHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(5)
        try:
            credentials = self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            pid, peer_uid, gid = struct.unpack("3i", credentials)
            if pid <= 0 or peer_uid != os.getuid():
                self._reply({"status": "denied"})
                return
            raw = self.rfile.readline(MAX_REQUEST_BYTES + 1)
            if not raw.endswith(b"\n") or len(raw) > MAX_REQUEST_BYTES:
                self._reply({"status": "denied"})
                return
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=self._unique_pairs,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            self._reply(self.server.dispatch(value, peer_uid))
        except (OSError, TimeoutError, UnicodeError, ValueError, RecursionError):
            try:
                self._reply({"status": "denied"})
            except OSError:
                pass

    @staticmethod
    def _unique_pairs(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError("duplicate")
            result[k] = v
        return result

    def _reply(self, value: dict) -> None:
        data = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        if len(data) > MAX_RESPONSE_BYTES:
            data = b'{"status":"unverifiable"}'
        self.wfile.write(data + b"\n")


def client(root: str | Path, *, workspace: str, digest: str, action: str,
           plan_path: str | None = None) -> dict:
    directory = _root(root)
    token = _token_file(directory)
    args = {"action": action, "token": token, "workspace": workspace, "digest": digest}
    if plan_path is not None:
        args["plan_path"] = plan_path
    raw = json.dumps(args, separators=(",", ":")).encode() + b"\n"
    if len(raw) > MAX_REQUEST_BYTES:
        raise WorkspaceDenied("operator-request-too-large")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(8)
        sock.connect(str(directory / SOCKET_NAME))
        sock.sendall(raw)
        reply = bytearray()
        while len(reply) <= MAX_RESPONSE_BYTES:
            piece = sock.recv(2048)
            if not piece:
                break
            reply.extend(piece)
            if b"\n" in piece:
                break
        if len(reply) > MAX_RESPONSE_BYTES or not reply.endswith(b"\n"):
            raise WorkspaceDenied("invalid-operator-response")
        result = json.loads(reply)
        if not isinstance(result, dict) or not isinstance(result.get("status"), str):
            raise WorkspaceDenied("invalid-operator-response")
        return result
