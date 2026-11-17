# Stage D / Phase 36 — Standalone offline mobile ciphertext readback

**Implementation boundary:** a single downloadable HTML file, `web/stage-d-mobile-readback.html`, designed for a modern mobile browser with local file access and WebCrypto SHA-256. It contains its JavaScript and CSS inline, with no dependency on a server, account, external CDN, build tool or private key. No production Railway data or owner ciphertext were used in implementation tests.

## The precise usability gap

Phase 35's trusted two-filesystem POSIX verifier correctly refuses two directories on a single filesystem. A phone-only owner may not have two independent POSIX mounts or a terminal. This new page gives the owner **a local browser-level byte comparison**, but does not replace or weaken the Phase 35 custodian separation or the Phase 35 requirement for independent offsite custody. The browser cannot prove that selected files were ever copied to separate physical devices.

## Run on Android or desktop

1. Download the **single exact source file** `web/stage-d-mobile-readback.html` from a reviewed commit and save it privately on your device. Open it as a local HTML document in a modern browser that supports file selection and WebCrypto. Some Android file handlers disable scripts or local WebCrypto; if `webcrypto_unavailable`, stop — **do not upload the encrypted backup to an online hash website**. The app requires no login and should be usable offline once opened. Do not enter API keys, passwords or decryption keys.
2. On GitHub independently find the completed **manual** `NEXUS Stage D — Manual Encrypted Volume Capture` workflow run on `main`. Confirm its exact run ID, attempt number, commit SHA, successful ciphertext upload and fresh-runner redownload. Copy the exact `NEXUS_ENCRYPTED_ESCROW_ANCHOR_V1` line from that run's log. A line saved beside a file is not an independently authenticated log.
3. Enter the independently inspected GitHub run ID, attempt and 40-character lowercase commit. Paste the original anchor line. The page rejects any mismatch between the line and those user-supplied values.
4. Select Copy A's `.cms` ciphertext and matching JSON receipt. Repeat with separately downloaded Copy B. Neither pair is uploaded: the page reads each using the browser file API and calls local WebCrypto SHA-256.
5. Tap **Verify local bytes**. `MATCH` means the **two selected pairs** each match the exact SHA-256 and length declared in the copied run-log line, and their receipts retain the expected non-authority claims. `BLOCKED` means one or more integrity/structure checks could not be satisfied. The page does not display raw file contents, passwords or tokens. It cannot independently authenticate the origin of the pasted run-log line.

## Security and technical limits

- A restrictive HTML Content Security Policy prevents active external resource loads and connection APIs; all script and CSS are within the one HTML file. The user should still verify the HTML came from the reviewed repository because locally modified JavaScript could leak data if executed in an unrestricted context.
- The browser hashes a whole selected file with `crypto.subtle.digest`, so RAM use may be substantial for the maximum 65 MiB ciphertext. The UI blocks on unsupported WebCrypto or wrong length; it never silently falls back to network hashing. Receipt inputs are capped at 32 KiB and the run-log anchor at 4096 characters.
- The strict flat-JSON parser refuses duplicate keys, nested values, unexpected fields and authority escalation, and the exact bytes of each JSON receipt (not merely its interpreted values) must match the externally obtained run-log receipt SHA-256.
- A successful result **never claims** independent storage (browser file selection does not expose custody), successful cryptographic decryption, owner recovery-key possession, real Railway volume origin, atomic consistent capture, a complete production backup, a genuine successful GitHub run, isolated restore, or production release approval.
- Do not assume that selecting the same downloaded file twice creates independent custody. The user must preserve genuine separate encrypted copies outside GitHub's expiring seven-day artifact retention and separately prove key decryptability and isolated restore via the existing owner-controlled Stage D instructions.
- Opening as a `file://` document depends on browser and Android file-handler policy. Tests verify the pure JavaScript cryptographic contract in Node with synthetic bytes. An actual mobile browser/device acceptance test is **still required** before asserting verified Android compatibility.

## Tests and next hard gate

`node --test scripts/test-stage-d-mobile-readback.mjs` uses Node WebCrypto and synthetic non-CMS bytes to cover exact GitHub identity, dual-file hashes, source byte mutation, forged or duplicate JSON keys, missing/oversized data, WebCrypto unavailable and a strictly offline single-file CSP. Dedicated GitHub CI runs with `contents: read` only. A passing synthetic CI test does not create a real backup.

**Production remains BLOCKED** until a real authorized read-only Railway `/data` copy exists, the owner holds the matching private key, the independently retained encrypted ciphertext is re-read and decrypted, an isolated restored snapshot is tested, and a human authorizes any exact commit promotion. The current Railway volume and pending healthcheck changes are not modified by Phase 36. The authority invariant remains `A_out <= A_in`.
