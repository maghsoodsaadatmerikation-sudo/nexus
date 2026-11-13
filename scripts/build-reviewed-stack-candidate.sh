#!/usr/bin/env bash
set -euo pipefail
test "$GITHUB_ACTIONS" = true
test -z "$(printenv RAILWAY_TOKEN || true)"
test -z "$(printenv RENDER_API_KEY || true)"
test -z "$(printenv NEXUS_API_TOKEN || true)"
git fetch --no-tags origin \
 +refs/heads/main:refs/remotes/origin/main \
 +refs/pull/129/head:refs/remotes/origin/rehearsal-129 \
 +refs/pull/130/head:refs/remotes/origin/rehearsal-130 \
 +refs/pull/131/head:refs/remotes/origin/rehearsal-131 \
 +refs/pull/132/head:refs/remotes/origin/rehearsal-132 \
 +refs/pull/133/head:refs/remotes/origin/rehearsal-133 \
 +refs/pull/134/head:refs/remotes/origin/rehearsal-134
for pair in '129 130' '130 131' '131 132' '132 133' '133 134'; do
 set -- $pair
 git merge-base --is-ancestor "refs/remotes/origin/rehearsal-$1" "refs/remotes/origin/rehearsal-$2"
done
main_sha="$(git rev-parse refs/remotes/origin/main)"
git config user.name 'NEXUS Isolated Integration'
git config user.email 'nexus-integration@users.noreply.github.com'
git checkout --detach "$main_sha"
for n in 129 130 131 132 133 134; do
 git merge --no-ff --no-edit -s ort -X ours "refs/remotes/origin/rehearsal-$n"
done
git show refs/remotes/origin/rehearsal-134:artifact-05/src/lib.rs > artifact-05/src/lib.rs
python3 - <<'PY'
from pathlib import Path
import subprocess
p=Path('artifact-05/src/lib.rs')
feature=p.read_text()
main=subprocess.run(['git','show','refs/remotes/origin/main:artifact-05/src/lib.rs'],check=True,capture_output=True,text=True).stdout
start=main.index('async fn studio_model_status()')
stop=main.index('async fn web_workspace()',start)
handlers=main[start:stop]
assert 'async fn studio_workspace()' in handlers
anchor='        .route("/", get(web_workspace))'
assert feature.count(anchor)==1
feature=feature.replace(anchor,anchor+'\n        .route("/studio", get(studio_workspace))'+'\n        .route("/studio-api/status", get(studio_model_status))')
anchor='async fn web_workspace()'
assert feature.count(anchor)==1
p.write_text(feature.replace(anchor,handlers+anchor))
p=Path('artifact-05/Cargo.toml')
s=p.read_text()
anchor='edition = "2021"\n'
assert s.count(anchor)==1 and 'rust-version =' not in s
p.write_text(s.replace(anchor,anchor+'rust-version = "1.85"\n'))
# Clean one trailing empty line present in the historical Stage 24 workflow.
# This is source whitespace only; no workflow behavior is changed.
p=Path('.github/workflows/stage24-static-site.yml')
assert p.is_file()
p.write_text(p.read_text().rstrip()+'\n')
PY
export CARGO_RESOLVER_INCOMPATIBLE_RUST_VERSIONS=fallback
image='rust@sha256:0ff31c9ffa641a62e48d543fb00b4960955ea375f40776f40f585b89e654cc5e'
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp/home -e CARGO_HOME=/tmp/cargo \
 -e CARGO_RESOLVER_INCOMPATIBLE_RUST_VERSIONS=fallback \
 -v "$PWD:/app" -w /app "$image" cargo generate-lockfile --manifest-path artifact-05/Cargo.toml
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp/home -e CARGO_HOME=/tmp/cargo \
 -v "$PWD:/app" -w /app "$image" bash scripts/run_gates.sh
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp/home -e CARGO_HOME=/tmp/cargo \
 -v "$PWD:/app" -w /app "$image" cargo test --manifest-path artifact-05/Cargo.toml --locked
git add -A
git commit -m 'Review-only integration: six PRs, new gateway routes and Studio preservation'
git diff --check "$main_sha" HEAD
mkdir -p nexus-candidate
git diff --binary --no-ext-diff "$main_sha" HEAD > nexus-candidate/candidate.patch
test -s nexus-candidate/candidate.patch
python3 - "$main_sha" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path('nexus-candidate')
data=(p/'candidate.patch').read_bytes()
r={'schema':'nexus.integration.review-candidate.v1',
   'status':'SYNTHETIC_CORE_GATEWAY_PASS_PRODUCTION_BLOCKED',
   'base_main_sha':sys.argv[1], 'patch_sha256':hashlib.sha256(data).hexdigest(),
   'release_authorized':False,'provider_changed':False,
   'production_backup_recovered':False,'semantic_security_review_complete':False}
(p/'manifest.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
PY
echo 'TESTED CANDIDATE PATCH READY: NO RELEASE AUTHORITY'
