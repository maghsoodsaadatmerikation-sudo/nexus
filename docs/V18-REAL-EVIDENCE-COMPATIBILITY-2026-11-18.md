# v1.8 release-chain audit: real artifact compatibility correction

Date: 2026-11-18.

## Reproduced defect

The read-only parent/rebuild provenance validator previously required JSON
**integer** run IDs. The repository's real v1.8 evidence generator writes both
as JSON **strings**. The former synthetic tests used integers too, so they
would pass while the actual GitHub Actions evidence was rejected.

Independently downloaded public GitHub Actions evidence:
- Repository: `maghsoodsaadatmerikation-sudo/nexus`
- Rebuild workflow run: `44222980195` (success; first attempt)
- Parent NEXUS Verification run: `44222413691` (success; main push)
- Workflow candidate SHA: `1ee30f7784420f27bba5d5d5798d9cdf3b64c89f`
- Artifact ID: `14390824887`, artifact name
  `v1.8-independent-rebuild-evidence`
- Extracted original JSON entry size: 933 bytes
- Original JSON entry SHA-256:
  `220b08c8c41f875679cbb18044746dc00f7e3d16e8d5a411cd276a0fd02a4474`
- Both independently recorded gateway binary digest claims:
  `c6dd176f82b2789e669bcc5fc1f9e0cd47b569c46d888612457ca44f2166de32`

## Implemented correction

- `scripts/release-chain-v18-audit.py` now checks exact **canonical decimal
  strings** against the independently supplied parent/rebuild numeric IDs.
  Signs, whitespace, leading zeros, booleans, floats and integers in the
  JSON evidence are denied. This matches the current evidence writer's
  exact on-wire format, not a permissive auto-cast.
- `scripts/fixtures/v1.8-rebuild-evidence-main-2026-11-18.json` is a
  byte-for-byte copy of the downloaded source JSON artifact (not a signature
  or privileged authorization).
- The read-only PR test suite now asserts the fixture's **independent SHA-256
  fingerprint** and checks full two-hop consistency using its actual IDs,
  source SHA, and binary hash claims.
- Existing adversarial tampering and privilege assertions remain in place.

## Truth boundary

The fixture is *public historical evidence* and does not confer signing,
release, production mutation or deployment authority. The binary digests
are artifact claims; independently verifying the artifact's GitHub
attestation and actual build inputs remains a separate step. The manual
signed-evidence preflight added in the preceding PR is still unmerged.

The repeatedly observed Public Studio jobless Actions failures have not
been attributed to a specific YAML syntax cause. A zero-job failure does
**not** prove browser tests failed; root-cause diagnosis remains open.

Safe rollout: exact-head PR CI, then owner review of stacked PRs; no
automatic main merge, release or public deployment. `A_out <= A_in`.
