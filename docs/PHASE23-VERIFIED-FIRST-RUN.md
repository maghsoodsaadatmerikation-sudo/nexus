# Phase 23 — verified first run and atomic no-clobber install

The **installed** NEXUS operator pilot now has an integrity-first launcher.
It offers only three local actions: \`doctor\` (check installed files and OS),
\`check\` (non-executing local operator-root observation) and \`smoke\` (fixed,
explicitly approved synthetic operator cycle). It is **not** a user-facing
hosted ChatGPT replacement, public service, Android app, production installer,
autonomous execution agent, or security attestation. \`A_out <= A_in\`.

## Install a new private version

First obtain the *whole ZIP SHA-256* from a trusted **independent** source
for the exact GitHub Actions run/source revision. Self-declared hashes inside
the ZIP are not an identity or publisher signature. On nonroot Linux with
Python 3.13+:

~~~bash
mkdir -m 700 -p "$HOME/nexus-pilot-installs"
python scripts/nexus-operator-distribution.py install \
  --archive /path/to/verified/nexus-operator-pilot.zip \
  --expected-sha256 TRUSTED_EXACT_ZIP_SHA256 \
  --destination "$HOME/nexus-pilot-installs/pilot-23"
python -I -B "$HOME/nexus-pilot-installs/pilot-23/scripts/nexus-operator-launch.py" doctor
python -I -B "$HOME/nexus-pilot-installs/pilot-23/scripts/nexus-operator-launch.py" smoke --approve-disposable
~~~

The installer now uses Linux \`renameat2(RENAME_NOREPLACE)\` to **fail rather
than overwrite** a destination created between preflight and publication.
It never silently falls back to unsafe \`os.rename\`. Reinstall/upgrade
requires a **fresh** destination. No prior user file, workspace, archive,
journal, service socket or application version is overwritten or removed.

The launcher verifies installed file hashes and owner-only permissions
before delegating to the fixed pilot command. It executes with isolated
Python \`-I -B\`, without \`PYTHONPATH\` or user startup hooks, and does not
write \`__pycache__\` inside the verified installation. To observe an
existing user workspace without running a job:

~~~bash
python -I -B "$HOME/nexus-pilot-installs/pilot-23/scripts/nexus-operator-launch.py" \
  check --root /absolute/private/operator-root --workspace alpha
~~~

The \`check\` mode can create only a private 0600 host-admission flock
metadata inode. A clear observation does not establish host security,
Docker orphan absence, release approval, or model authorization.
\`smoke\` uses a fresh, disposable, fixed synthetic plan and requires
\`--approve-disposable\`; it does not run arbitrary user/model code.

## Trust and limits

A matching *operator-supplied SHA-256* is now reported as
\`archive_digest_matched=true\`; it does **not** prove who supplied that
hash. Consequently \`publisher_authenticated=false\` remains true in all
output until a real independent signing/verifying trust chain exists.
Installed-file integrity checks also are not publisher signatures.

The installed launch verifier and files reside under one account and
cannot prevent races or hostile replacement by a same-UID adversary.
Root, non-Linux, missing dependencies, corrupted files, unsafe destinations,
implicit smoke requests, and mismatched archive hashes remain fail-closed.
The release candidate stays on PR #244 as Draft/unmerged; there is no
automatic background process, public deployment or browser/Docker socket.
