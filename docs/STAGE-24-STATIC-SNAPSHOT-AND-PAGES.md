# Stage 24 — static-only GitHub Pages source and independent HTTPS verification

## Observed blocker and release boundary

The original NEXUS repository is public, but GitHub reported has_pages: false at the start of this stage. Pages source selection is an account setting, not a code change. The available GitHub connector does not expose an operation to enable those settings. The static site must not be described as deployed until HTTPS public byte verification succeeds.

The Stage 24 change delivers a source branch containing ONLY a reviewed mobile Work Mode PWA, plus a no-credential observer that can independently inspect the eventual public HTTPS version.

It does not touch protected Railway data or original /data volume, current Render services, main, paid resources, user files or private credentials. Original-volume recovery Issue #104 and real authenticated-human pilot Issue #70 remain open.

## What the automation does

- The Python publisher checks the Git blob identities of eight previously reviewed Stage 23 inputs: the two icons, Work Mode HTML and core JS, and the generator and test files.
- It rebuilds the site deterministically and accepts exactly seven files: index.html, manifest.json, service-worker.js, two PNGs, nexus-stage23-integrity.json and an empty .nojekyll. Unexpected files, directories containing files, tampering or symlinks are rejected.
- CI reruns the privacy/source tests, Stage 23 PWA tests and real desktop Chromium tests with synthetic encrypted projects, tamper rejection, two hosting scopes and true network disconnection.
- On pull requests CI is read-only. Once the PR is merged into feat/work-mode-20261113, a separate job with contents:write runs ONLY if the verification job passes on that exact push. It downloads and rechecks the approved artifact, then creates an ORPHAN branch named nexus-mobile-site-v24 containing exactly those seven files, no source history, no backend files or workflows. An existing branch is not overwritten. Force-push is forbidden.
- It creates a public GitHub repository SOURCE SNAPSHOT. It does not enable GitHub Pages, configure domains or deploy to HTTPS.

Important GitHub restriction: a commit pushed using GITHUB_TOKEN does not itself trigger a GitHub Pages build. The branch creation alone must not be mistaken for an active website.

Official guidance:
https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site

## Minimal remaining action to actually publish

After verifying that the isolated branch exists:

1. Open GitHub repository Settings > Pages.
2. Under Build and deployment, select Deploy from a branch. Choose nexus-mobile-site-v24 and /(root), then Save. Pages is offered for public GitHub Free repositories.
3. Confirm a genuine Pages deploy appears in Actions. Since GITHUB_TOKEN pushes cannot trigger a Pages build, initial site-source selection may still require a normal, reviewed commit from an administrator with a verified email address to start publishing.
4. The expected site address, once actually live, is:
   https://maghsoodsaadatmerikation-sudo.github.io/nexus/
   This is a destination to check, NOT a verified live link.
5. Run the independent strict observer from the development source:

       python3 scripts/build-mobile-work-pwa.py --out build/stage24-site
       python3 scripts/stage24-static-publish-check.py --site build/stage24-site --public

   The observer makes read-only HTTP GET requests to seven fixed HTTPS paths only, including root and index. It enforces status 200, allowed MIME, no redirects, exact SHA/bytes and the known destination. Missing or altered assets return PUBLIC_NOT_VERIFIED and a nonzero exit code. A response from the site is not enough for a PASS.

6. Only AFTER exact public bytes pass, open the site on the actual Android device. Press Prepare offline to opt in; select Install app or Add to Home Screen in the browser, if supported. Create a fictional test project, save an encrypted archive, download an independent encrypted backup, turn off network access and confirm the saved project reopens. Do not rely on real private work until the device-specific test passes.

## Self-critique and separate acceptance gates

A standalone PWA is useful without a paid server but cannot provide generative model inference, third-party account logins, MCP tools, server search, authenticated Rust access or multi-device sync. A compromised hosting origin or browser can read the active plaintext. Encrypted local IndexedDB can be evicted or cleared. A securely kept, separately verified encrypted backup remains necessary.

The CI Chrome test is synthetic and is not proof of an actual Android phone test. Static GitHub branch verification is not a real HTTPS public deployment. No site release seal, original Railway backup/isolated restore or authenticated production launch is claimed. Final judgment remains human; A_out <= A_in.
