# Optional encrypted conversation history

Development change stacked on the source-grounded conversation branch. This is
not a deployment, server account history, cloud sync or production recovery proof.

## User choices

Open `/research-chat`. History is off and locked initially; merely opening the
page does not create or read a history database. Create an encrypted archive with
a passphrase of at least 12 characters, or unlock an existing one. API-token and
passphrase fields are never copied to history. Anything explicitly typed into
messages remains conversation content, including secrets typed there.

Saving and attaching history are separate opt-ins:

- **Save now** saves completed exchanges, citations and a title. The save checkbox
  additionally enables saving future successful replies in this conversation.
  Drafts, failed requests and query approval flags are excluded.
- Select a saved conversation and **Open and continue** to restore it locally;
  replacing an existing conversation or draft requires confirmation. Saving and
  attachment remain off after opening.
- Alternatively select a conversation and check **Attach selected history** to
  give a later conversation its last six messages and up to two source passages.
  Nothing is sent until Send. Changing the selection detaches history. It is
  attached only to this NEXUS server; only the separately approved exact search
  query can reach providers. A user can explicitly copy private text into that
  query, so query approval remains essential.
- Locking drops the archive key and detaches selected history. Already opened
  chat text remains visible in the current tab until Clear, token change or close.
  Changing the API token locks history and clears current conversation context.
- Delete one saved conversation or all saved history with confirmation. Deleting
  an open saved conversation clears its active copy. Deleting the archive stops
  automatic saves; downloaded copies are unaffected.

Save/attach choices and unlock keys are not persisted. Reloading requires another
unlock and another choice. Nothing automatically retrieves an old conversation.
English and Persian interfaces are available. The gateway does not store history
or equate people sharing a bearer token with a single user account.

## Persistence and portability

The whole archive, including titles and timestamps, is encrypted in IndexedDB on
this browser/profile and origin. HTTPS (or localhost for tests) and Web Crypto
are required. Limits are 20 conversations, 40 completed exchanges per conversation,
and 4 MiB of serialized plaintext. Only valid alternating human/assistant turns
and known reply fields can be restored. Unknown credential/authority fields are
excluded. Oversized or malformed files are rejected.

Download encrypted history for backup or transfer; restore it with the same
passphrase on another browser/device. Import explicitly replaces the local archive
only after authentication, shape validation and successful storage commit. It
never enables automatic saving or attachment. Downloads are encrypted, unlike
the separate explicitly confirmed plaintext transcript export.

Browser clearing, eviction, private-browsing cleanup or an origin change can make
local history unavailable. Forgotten passphrases cannot be recovered. Successful
download preparation does not prove the file was retained on a device.

## Cryptography and failure behavior

AES-256-GCM uses a fresh 96-bit IV for every write. A non-extractable key is derived
using PBKDF2-HMAC-SHA256, 310,000 iterations, with a random 128-bit salt. Schema,
KDF metadata, salt and random revision are authenticated. No key/passphrase/token
is persisted. An authenticated envelope is bounded before expensive decryption.
This protects stored copies; it cannot protect plaintext from scripts executing
in the same trusted origin or from a compromised browser while unlocked.

An IndexedDB read/write transaction compares the expected revision before writing.
A stale tab is locked instead of overwriting another tab's archive. Operations are
serialized and invalidated by lock/token changes before commit. Failed storage
or quota checks never fall back to plaintext or change the in-memory saved state.
Current unsaved chat remains available; no successful-save message is shown.

## Historical context and NEXUS authority

`history_context` is optional on `POST /v1/research-chat`, carrying an identifier,
1–6 bounded human/assistant messages and at most two reviewed source passages.
It never accepts a system role. All history is client-supplied, unverified context,
not authenticated evidence or a stored identity. Responses expose
`history_context_attached`, `context_origin` and historical source origins.
Historical excerpts receive no fresh retrieval timestamp. No history text can
alter policy, execute actions or change human judgment. Provider calls continue
to receive only the exact approved query and selected search language.

## Verification

Node tests cover no default storage, key-field exclusion, encryption, password and
tamper rejection, portable restore, nonce rotation, storage failures, stale tabs,
locking races, deletion, role validation and capacity. Gateway tests cover selected
history provenance, exact-query isolation and role rejection. A real Chromium
fixture exercises the page's opt-ins, IndexedDB, save/unlock, attachment, reopening,
backup/import, storage failures, token changes and deletion on narrow/wide layouts.
All fixtures are synthetic and require no production credentials.
