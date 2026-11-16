#!/usr/bin/env python3
"""Real, isolated Docker acceptance on a disposable CI runner; no mock Docker."""
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from agent_workspace import Workspace, run_container


def main():
    image = os.environ["NEXUS_TEST_IMAGE_DIGEST"]
    assert "@sha256:" in image, "CI image must be digest-addressed"
    assert os.getuid() != 0, "Docker acceptance must not use root"
    with tempfile.TemporaryDirectory(prefix="nexus-docker-acceptance-") as temp:
        root = Path(temp) / "private"
        root.mkdir(mode=0o700)
        ws = Workspace(root, "test")
        ws.write("hello.txt", b"NEXUS-runtime")
        success = run_container(ws, image, ["sh", "-c",
                   "cat hello.txt; id -u; printf generated > output.txt"],
                   approved=True, timeout_seconds=15)
        assert success.status == "complete" and success.exit_code == 0, success
        assert "NEXUS-runtime" in success.stdout and str(os.getuid()) in success.stdout
        assert ws.read("output.txt") == b"generated"

        immutable = run_container(ws, image, ["sh", "-c", "echo escape > /host-write-test"],
                                  approved=True, timeout_seconds=15)
        assert immutable.status == "complete" and immutable.exit_code != 0, immutable
        assert not (Path(temp) / "host-write-test").exists()

        # A long-running child must be terminated and its Docker container
        # cleaned up when the timeout expires.
        deadline = run_container(ws, image, ["sleep", "7"],
                                 approved=True, timeout_seconds=1)
        assert deadline.status == "timeout" and deadline.exit_code == -1, deadline
        assert ws.manifest()["file_count"] == 2

        # A second operator process can set this event while Docker is active.
        # This verifies the live CLI/container cleanup path, not just mocks.
        signal = threading.Event()
        trigger = threading.Timer(1.0, signal.set)
        trigger.start()
        try:
            stopped = run_container(ws, image, ["sleep", "25"],
                                    approved=True, timeout_seconds=30,
                                    cancel_event=signal)
        finally:
            trigger.cancel()
        assert stopped.status == "cancelled" and stopped.exit_code == -1, stopped
        assert ws.manifest()["file_count"] == 2
        print("NEXUS real Docker acceptance PASS (nonroot, write, rootfs deny, timeout, cancel, cleanup)")


if __name__ == "__main__":
    main()
