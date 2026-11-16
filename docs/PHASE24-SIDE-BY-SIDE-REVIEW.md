# Phase 24 — pinned installation review and safe side-by-side candidate inspection

NEXUS adds a **non-executing** version comparison for the private operator
pilot. It never changes the installed version, workspace, journals, host
daemon, active service, or executable privileges. There is no "upgrade" or
"rollback" action: human review and a separately approved installation
directory are mandatory.

## What is checked

`verify-installed` now validates: private owner-only installation parent,
root directory, every subdirectory, owner-only regular files (no symlinks or
hardlinks), canonical manifest fields, exact file allowlist and per-file hashes.
It can optionally compare its canonical `bundle-manifest.json` SHA-256 to an
**independently supplied** expected value. Without that out-of-band digest,
internal file hashes are integrity observations, not proof of publisher identity.

`compare-installed` takes two existing, separately installed private
directories; the new candidate **must** have an out-of-band expected manifest
digest. Both trees must individually pass full integrity checks; it rejects
a missing/modified/corrupt/symlinked installation and refuses to compare
one path to itself. It returns only the allowlisted changed file names,
counts, the two manifest hashes and explicit non-authority indicators.
It never displays file contents, private data or credentials; no file is
modified and no newly installed code is run.

## Non-destructive procedure (Linux, unprivileged, Python 3.13+)

From a trusted checkout, first verify the new candidate ZIP against its
independently obtained exact SHA-256 and install it **to a new directory**
with the existing Phase 23 installer:

```bash
python scripts/nexus-operator-distribution.py install \
  --archive /trusted/download/pilot-next.zip \
  --expected-sha256 TRUSTED_ZIP_SHA256 \
  --destination "$HOME/nexus-pilot-installs/next"
```

Obtain `MANIFEST_SHA256` independently from the GitHub Actions build record
for the **same** source commit/ZIP. Matching a user-provided hash is not
cryptographic proof of which person or project published that hash.

```bash
python -I -B scripts/nexus-operator-distribution.py compare-installed \
  --current "$HOME/nexus-pilot-installs/current" \
  --candidate "$HOME/nexus-pilot-installs/next" \
  --expected-candidate-manifest-sha256 MANIFEST_SHA256

python -I -B "$HOME/nexus-pilot-installs/next/scripts/nexus-operator-launch.py" \
  doctor --expected-manifest-sha256 MANIFEST_SHA256
```

If you have separately preserved the old manifest digest, add
`--expected-manifest-sha256 OLD_MANIFEST_SHA256` to the compare command.
Review each changed file and the release evidence *before* manually using
the new version. There is deliberately **no automatic switchover**, no
upgrade in place, no cleanup/removal of the old installation, and no
migration of user workspaces or journal receipts.

For controlled acceptance, the fixed disposable
`smoke --approve-disposable --expected-manifest-sha256 MANIFEST_SHA256`
can verify the new installation without touching your project.

## Security scope

- `manifest_anchor_matched=true` means an independently supplied SHA-256
  matched the bytes; `publisher_authenticated=false` always remains true
  until there is a separate signing identity and verification chain.
- An attacker controlling the operator UID, host root, expected digest source
  or the Python interpreter is **outside the security guarantee**.
- The report's `upgrade_authorized=false` means **no execution or migration
  permission**, even if the file sets match exactly.
- The exactly enumerated **Phase 22 and Phase 23** installed file
  inventories can be reviewed side by side with Phase 24, without running
  legacy code. The report separates `added_paths`, `removed_paths` and
  `modified_paths`; an unfamiliar inventory is always refused rather than
  interpreted or migrated.
- No production server, Docker, Android app or browser bridge is created.
- This stage is still on Draft PR #244. CI validates the private installation
  and comparison on ephemeral Ubuntu only; it does not certify production
  systems.


## Phase 25 — one-snapshot ZIP verification and install (regression fix)

Before Phase 25, the ZIP pathname could be opened once to hash the archive
and then opened again to validate or extract members. If a file at that path
was replaced between operations, the hash-validated bytes might not be the
bytes actually inspected or installed.

The distribution verifier now obtains one bounded regular-file snapshot using
a no-follow file descriptor, verifies the external archive SHA-256 and every
manifest/member from **that same in-memory snapshot**, and installs only from
those verified bytes. The installer no longer reopens the ZIP pathname after
validation. This is a check/use race fix, not broader host isolation.

Regression tests exercise a replaced ZIP pathname immediately after a
snapshot is taken, replacement after full hash and manifest verification,
and rejection of a symlinked input ZIP. Existing deterministic bundle,
no-clobber installation and read-only comparison tests still apply.

**Boundaries:** This does not authenticate a publisher, prevent a hostile
same-UID process from modifying installed code, make source-tree reads atomic,
or certify a production deployment. Install remains explicit, nonroot,
Linux/Python 3.13+, with an independent whole-archive digest and a new
private destination. PR #244 stays Draft until exact-head CI passes.


## Phase 26 — source-tree read hardening for reproducible builds

The operator bundle builder previously checked each source path with `lstat`
and then opened it again by pathname, leaving a replace-after-check window.
The source reader now opens the repository root and each allowlisted directory
component using directory file descriptors and `O_NOFOLLOW`. Each file is
opened relative to its pinned parent directory with `O_NOFOLLOW`, required
to be a single-link regular file, and read with the existing per-file size
ceiling. File size and metadata (device/inode, size and high-resolution
modification/change time) are checked again after the read. A detected
in-place mutation causes the build to be denied before a ZIP is created.

Tests cover symlinked source files/directories/root, hardlinked file inputs,
a malicious final-path swap immediately before open, and mid-read mutation.
The existing reproducible double-build, verified-install and smoke tests remain
the CI acceptance gate.

**Limits:** A directory-handle walk and per-file metadata comparison do not
provide an atomic snapshot of the entire checkout. A same-UID hostile process,
mutating checkout between distinct files, or a compromised build runner remain
outside the pilot's assurance. For release provenance, use an isolated
immutable commit checkout and independently attest the source commit and
final ZIP digest. No model, browser or Docker privilege was expanded here.
