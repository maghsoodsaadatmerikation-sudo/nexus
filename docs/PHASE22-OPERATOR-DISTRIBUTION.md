# Phase 22 — reproducible, inspectable local-operator pilot bundle

**Scope:** nonroot Linux/Python 3.13 pilot, not an automated AI tool,
production installer, website deploy, or multi-tenant capability. Release
promotion still requires an independent operator decision. PR #244 is Draft.

## What this actually provides

A deterministic ZIP builder with an explicit allowlist of operator-only
modules, CLIs, a reviewed static proof source and safety documentation.
Everything is stored without compression, in sorted order, with a fixed ZIP
timestamp and 0600 file modes. No Docker images, daemon sockets, API secrets,
user files, dependency downloads or mutable git history are packaged.

The manifest names every file with an exact SHA-256 and byte count. The
verifier rejects extra/duplicate/traversal-like ZIP entries, unknown sources,
symlinks, compressed entries, forged metadata or mismatched content. The
whole archive SHA-256 is reported separately. **Internal hashes do not
authenticate the archive publisher.** For installation the operator MUST
obtain the archive digest independently from a trusted release/CI channel
and supply it explicitly. A SHA text file delivered in the same untrusted
archive does not establish independent provenance.

The installer only accepts a *new* destination beneath an existing owner-only
0700 parent, walks parent directories without following symbolic links,
verifies the complete archive, stages private files, checks their digests
again, and atomically moves them into place. It never overwrites an old
installation, starts an agent, creates production workspaces, asks for root
privileges, opens a public port, or runs bundled code implicitly.

An installed copy can be checked using \`verify-installed\`; this detects
accidental or unauthorized content changes but is **not a cryptographic
signature**: a hostile same-UID process could replace both files and manifest.

## How to build, verify and install (operator controls)

On a nonroot Ubuntu/Linux terminal with Python 3.13, from a trusted NEXUS
checkout (review the pinned Git commit first):

~~~bash
mkdir -m 700 -p "$HOME/nexus-pilot-installs"
python scripts/nexus-operator-distribution.py build \
  --source . --output "$HOME/nexus-pilot-installs/pilot-bundle.zip"
python scripts/nexus-operator-distribution.py verify \
  --archive "$HOME/nexus-pilot-installs/pilot-bundle.zip"
~~~

An independent trusted source (e.g. a separately reviewed GitHub Actions run
for the **exact** source commit) must supply \`EXPECTED_ARCHIVE_SHA256\`. It
is **not** sourced from the untrusted ZIP or its self-declared manifest.

~~~bash
python scripts/nexus-operator-distribution.py install \
  --archive "$HOME/nexus-pilot-installs/pilot-bundle.zip" \
  --expected-sha256 EXPECTED_ARCHIVE_SHA256 \
  --destination "$HOME/nexus-pilot-installs/installed-v1"
python "$HOME/nexus-pilot-installs/installed-v1/scripts/nexus-operator-distribution.py" \
  verify-installed --destination "$HOME/nexus-pilot-installs/installed-v1"
python "$HOME/nexus-pilot-installs/installed-v1/scripts/nexus-operator-pilot.py" \
  smoke --approve-disposable
~~~

\`smoke\` is a **fixed synthetic operator-only test**, not model code execution.
It uses a real private Unix socket and one-use journal in a disposable 0700
root, validates the terminal receipt and replay denial, and removes its
temporary files. Use \`check --root /absolute/0700/operator-root\` to
observe an already-existing operator root; this creates only a private
admission lock metadata inode, never starts a job.

Do not run \`install\` as root. To upgrade, choose a **fresh new** installation
directory; compare hashes and review changes before altering operator
workflows. There is intentionally no automatic in-place upgrade or rollback.
The bundle is not a mobile Android application or hosted public service.

## CI quality gate

Dedicated \`operator-distribution\` CI performs: two full builds with
byte-for-byte comparison; archive verification against the explicit digest;
private installation; post-install source verification; execution of the real
synthetic smoke using the **installed** CLI; and a negative attempt to install
with the wrong SHA. Separate Python regression tests exercise archive tamper,
entry type, duplicate/unknown entries, symlink traversal, private directory
permissions, changed installed files and refusal to overwrite.

The read-only-permission CI workflow uploads the deterministic ZIP, the
standalone verifier/installer script and a SHA256SUMS report as a GitHub Actions
artifact. Artifacts are release **candidates**, not attested published
releases. The archive SHA must be compared with a trusted, exact-run
source; this tool does not create a digital signature.

Passing does not prove runtime isolation on a real operator's host, Docker
orphan absence, browser/backend connectivity, hardware support, license
compliance or production security. No automatic deploys or merges.
