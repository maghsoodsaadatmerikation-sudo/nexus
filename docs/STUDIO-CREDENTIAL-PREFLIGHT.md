# NEXUS Studio — local credential preflight

A source-level, best-effort check for possible credentials when a user prepares an exact request for a remote model.

## Behavior

- Scan the actual prepared messages, including opted-in conversation history, reviewed memory, local source excerpts and one-turn attachments.
- Recognize bounded high-confidence patterns: PEM private-key header, GitHub personal-access token, model API key, AWS access key identifier and HTTP bearer credential.
- Show only built-in category labels, **not the matching secret values**. No added network call, logging, persistence, automatic masking or upload.
- In remote gateway mode, block the send control unless **both** the original exact-context consent and the separate credential-warning acknowledgement are checked. Revalidate in the click handler too.
- Regeneration, navigation, changing the pending request or clearing the review revokes the extra consent. On-device mode is unaffected.

## Limitations

This is **not comprehensive data-loss prevention**: novel, encoded, split, incomplete or custom credentials and many types of personal information can be missed, and synthetic examples may trigger a warning. Users should remove sensitive material and prepare a new request. Client-side scanning is not a server authorization boundary.

## Verification

```sh
node scripts/test-studio-core.mjs
python3 scripts/build-studio.py --check
python3 scripts/build-studio-static.py --check
```

Synthetic tests use invented strings; no live provider, real keys, deployment, production data or publication. Release remains subject to exact-head CI and separate human review.
