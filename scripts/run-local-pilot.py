#!/usr/bin/env python3
"""Supervise one loopback-only NEXUS pilot with private persistent local state."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request


def private_directory(path, create=True):
    if create:
        try:
            path.mkdir(mode=0o700, parents=True)
        except FileExistsError:
            pass
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError('state and data directories must be owner-only real directories')


def check_private_file(fd):
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077 or info.st_nlink != 1):
        raise ValueError('state files must be private regular files owned by this user')


def stored_token(path):
    flags = os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(path, flags | os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        fd = os.open(path, flags | os.O_RDONLY)
        try:
            check_private_file(fd)
            value = os.read(fd, 66)
        finally:
            os.close(fd)
        if re.fullmatch(rb'[0-9a-f]{64}\n', value) is None:
            raise ValueError('existing token is invalid; it was not replaced')
        return value.decode().strip()
    try:
        check_private_file(fd)
        value = secrets.token_hex(32)
        with os.fdopen(fd, 'wb', closefd=False) as handle:
            handle.write((value + '\n').encode())
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=Path(__file__).resolve().with_name('nexus'))
    parser.add_argument('--state-dir', type=Path,
        default=Path.home() / '.local' / 'share' / 'nexus-local-pilot')
    parser.add_argument('--port', type=int, default=3000)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument('--backup', type=Path, metavar='ARCHIVE',
        help='capture complete data while holding the operator lock; never overwrite')
    operation.add_argument('--restore', type=Path, metavar='ARCHIVE',
        help='restore into absent state/data with recovery quarantine')
    parser.add_argument('--offline', action='store_true',
        help='assert all writers, including raw binary invocations, are stopped')
    args = parser.parse_args()
    maintenance = args.backup is not None or args.restore is not None
    if maintenance and not args.offline:
        parser.error('backup/restore requires --offline after stopping every writer')
    if args.offline and not maintenance:
        parser.error('--offline applies only to --backup or --restore')
    if not 1024 <= args.port <= 65535:
        parser.error('port must be between 1024 and 65535')
    process = None
    lock_fd = None
    stopped = False

    def request_stop(signum, frame):
        nonlocal stopped
        stopped = True
        if process is not None and process.poll() is None:
            process.terminate()

    try:
        state = args.state_dir.absolute()
        private_directory(state, create=args.backup is None)
        lock_fd = os.open(state / 'operator.lock',
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        check_private_file(lock_fd)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('this pilot state is already in use') from None
        if maintenance:
            data = state / 'data'
            if args.backup is not None:
                private_directory(data, create=False)
                command = ['backup', str(data), str(args.backup)]
            else:
                command = ['restore', str(args.restore), str(data)]
            # The existing bounded tool validates all records, refuses overwrite,
            # and quarantines every restore. It captures no operator token/lock.
            result = subprocess.run([sys.executable,
                str(Path(__file__).resolve().with_name('data-snapshot.py')),
                *command, '--offline'], pass_fds=(lock_fd,))
            return result.returncode
        binary = args.binary.resolve(strict=True)
        token_path = state / 'api-token'
        token = stored_token(token_path)
        data = state / 'data'
        private_directory(data)
        env = dict(os.environ, NEXUS_API_TOKEN=token, NEXUS_DATA_DIR=str(data),
                   NEXUS_BIND_ADDR='127.0.0.1:' + str(args.port))
        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        # Keep the advisory lock alive in the child if the supervisor is killed.
        process = subprocess.Popen([str(binary)], env=env, pass_fds=(lock_fd,),
                                   stdout=sys.stderr, stderr=sys.stderr)
        if stopped:
            process.terminate()
            return 0
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = 'http://127.0.0.1:' + str(args.port)
        deadline = time.monotonic() + 10
        while not stopped and time.monotonic() < deadline:
            if process.poll() is not None:
                raise ValueError('gateway exited before startup completed')
            try:
                request = urllib.request.Request(base + '/v1/workspaces/local-pilot-startup-probe',
                    headers={'authorization': 'Bearer ' + token})
                try:
                    response = opener.open(request, timeout=1)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    if response.status not in (200, 404):
                        raise OSError('authenticated startup probe failed')
                try:
                    response = opener.open(base + '/readyz', timeout=1)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    readiness = response.status
                    if readiness not in (200, 503):
                        raise OSError('readiness probe failed')
                if process.poll() is not None:
                    raise ValueError('gateway exited during startup')
                print(json.dumps({'url': base, 'gateway_pid': process.pid,
                    'state': 'ready' if readiness == 200 else 'recovery-quarantined',
                    'token_file': str(token_path), 'authority': 'none'}), flush=True)
                code = process.wait()
                return 0 if stopped else code if code > 0 else 1
            except OSError:
                time.sleep(.05)
        if stopped:
            return 0
        raise ValueError('authenticated gateway startup timed out')
    except (OSError, ValueError) as error:
        # Never print credentials or server response bodies.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print('NEXUS LOCAL PILOT: BLOCKED (' + message + ')', file=sys.stderr)
        return 1
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if lock_fd is not None:
            os.close(lock_fd)


if __name__ == '__main__':
    raise SystemExit(main())
