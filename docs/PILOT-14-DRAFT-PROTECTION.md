# Pilot 14 — protect uncommitted form input

A person can type their first question without registering it. Previously,
New Workspace, a valid imported file, or a local-vault restore could overwrite
that first draft without confirmation because the workspace had no events.

The workshop now displays the names of sections with unregistered text,
provides a shortcut back to the first such section, and checks both committed
work and uncommitted text before New, Demo, file import and local restore.
Cancelling preserves both the workspace and the fields. The guard compares
forms with the committed workspace, so registered fields are not mistaken for
drafts. Password fields are never included in draft detection or messages.

If text changes while an encrypted local checkpoint is being opened, the
restore is aborted before replacing the workspace or fields. Successful
registration/import/restore refreshes the indicator. Creating a new workspace
or a confirmed replacement deliberately discards prior drafts.

Encrypted export explicitly warns when drafts are excluded. Existing plaintext
and Rust-export confirmations also state this boundary. Reports, exports and
the encrypted local checkpoint still contain only committed information;
**a draft never becomes an explicit human judgment automatically**.

A beforeunload listener is attached only while text drafts exist. Browsers may
ignore it without user activation or on mobile app termination; it is not a
recovery mechanism or guarantee against OS kills. No draft, password, key or
new plaintext store is persisted. For recovery, register text and use the
existing encrypted checkpoint/file features.

## Verification and deployment

A dedicated disposable real-Chromium witness covers narrow/wide layouts,
first-question replacement cancellation, source/option/decision drafts,
password exclusion, import normalization, explicit registration, export
exclusion, the encrypted-restore race, encrypted-vault continuity and absence
of new storage. Existing workshop/report/Rust/offline-browser witnesses remain
separate. Public acceptance must be pinned to the actually deployed source;
local candidate tests are not public or real-human acceptance.

Deploy only to the existing free static service after required checks pass.
No new provider resource, original Railway volume operation or release Seal.
Independent original-volume recovery (#104) and authenticated real-human
server acceptance (#70) remain separate open milestones. A_out <= A_in.
