# NEXUS Work Mode

Development feature stacked on optional MCP app connections (#133). No main merge,
production deployment, cloud project sync or autonomous execution is claimed.

## Workflow

Open `/work-mode` from the gateway home, conversation or app page. The page makes
no automatic API or provider request and opens no database. Enter a title, goal, success
criteria and your own newline-separated initial steps. These become pending tasks;
this is user-authored planning, not generated analysis or an executed task.

Choose a task and edit its title, status, prerequisite tasks, evidence and optional
file references. States are `todo`, `doing`, `blocked`, `review`, `done`. Cyclic,
self, missing or duplicate dependencies are rejected before adopting a change.
Starting requires completed prerequisites. Marking Done requires explicit human
review, evidence text or an attached file, and completed prerequisites. Reopening
a completed prerequisite is blocked while its dependents remain completed: reopen
the dependents first. Editing a goal or criteria returns completed tasks to review
and blocks in-progress work whose prerequisites are no longer complete. Counts
reflect local user-reviewed state, not independent verification of the real work.

Apply edited project/task fields before saving, exporting or preparing task context.
New notes/tasks must be added first. Failed validation retains the current project
and editor contents. Task switching prompts before discarding unapplied edits.
Unsaved work triggers a browser unload prompt where browser policy permits it.

Add human notes and attach files. Each file is held as bytes in the project, never
executed, actively previewed, parsed as instructions or automatically uploaded.
Only explicit download writes it to a user-selected device location. File download
uses application/octet-stream and a path-free bounded filename. A file referenced
by task evidence cannot be removed until its references are removed/reviewed.
Machine replies may be explicitly retained as `machine_draft` notes; they cannot
change task states, policies, workspace judgment or core execution authority.

The local activity list records up to 200 changes. It is a convenience record,
not a tamper-proof audit, replay proof, trusted identity or independent attestation.

## Persistence and portability

Projects initially exist only in RAM. Create or unlock an optional encrypted local
archive with a passphrase of at least 12 characters, then explicitly Save. No
background or automatic save is enabled. Unlocking shows a catalog but loads no
project: choose one and Open to resume. Lock clears the key, project, editors,
API-token field and chat results, cancelling late application of asynchronous work.
Changing the API token stops pending chat and revokes its approvals; it does not
silently erase a local project or sign into a different project account.

Download the encrypted archive to retain or transfer projects, including files.
Restore authenticates and validates it before replacing local archive data, rotates
the encryption revision/IV and never auto-opens a project. An existing RAM project
is retained and marked unsaved after archive replacement. Delete a selected saved
project or all projects with confirmation; downloaded copies remain independent.
A separate explicitly confirmed Markdown report is plaintext and excludes file
bytes and credential fields; it is not a complete restorable project backup.

The archive uses AES-256-GCM, PBKDF2-HMAC-SHA256 with 310,000 iterations, random
128-bit salt and fresh 96-bit IV/revision per write. Key material is non-extractable
and RAM-only. Schema/KDF/salt/revision metadata are authenticated. IndexedDB stores
only the encrypted envelope, including encrypted titles, goals, notes and files.
Atomic revision comparison prevents stale tabs from overwriting newer data.
Serialization and lock guards stop stale queued operations before commit. Storage
or quota errors preserve unsaved work and never fall back to plaintext storage.

The work archive has its own schema, database and authenticated encryption domain,
separate from chat history; neither archive can be imported as the other. API-token
and passphrase input fields are excluded. Secrets deliberately typed in project
text remain project data. Same-origin scripts or a compromised unlocked browser
can still access RAM plaintext; this is not protection from an active compromise.

Limits: 20 saved projects, 60 tasks/project, 12 criteria, 60 notes, 12 files/project,
1 MiB/file, 2 MiB of file bytes/project, 4 MiB serialized plaintext/archive, 6 MiB
maximum encrypted import file. JSON schema/roles, IDs, graph, review gates, filenames
and base64 are revalidated on restore. Browser/profile/origin clearing or eviction
can remove the local archive; keep a separate encrypted backup and passphrase.
Forgotten passphrases cannot be recovered. Download preparation does not prove
that a user retained the file. There is no server-side project account storage.

## Explicit conversation and app boundaries

Prepare selected task context to populate an editable preview of at most 1,500
characters: a bounded goal, first three criteria and current task title. Files,
notes, evidence text, full activity, archive keys and conversation history are not
included. Nothing is sent until a token and single-use sharing approval accompany
Send. Users can deliberately edit the message to include additional private data.
A manually reviewed public HTTPS source can be attached through the separate
source fields. Optional Wikipedia/DuckDuckGo retrieval requires its own exact-query
approval, consumed at dispatch even on error. Editing inputs, changing task/project,
locking/clearing or changing language revokes approval and discards late replies.

The existing `/v1/research-chat` endpoint performs extractive source-based answering,
not generative planning or autonomous execution. Its authentication-before-body,
no-store, body/rate/concurrency and quarantine boundaries remain. Failed requests
retain inputs and never retry automatically. The response changes no project task.
Keep a reply only through the explicit machine-note button. Work Mode links to
`/connections`; app use retains its separate per-call enablement/consent. There is
no background plugin execution, scheduler, terminal, arbitrary code execution,
file deployment, payment, message sending or automatic approval in this feature.

## Verification

Node tests cover planning without side effects, human completion gates, graph
validation, invalidated completions after goal changes, bounded/private context,
non-authoritative machine notes, file limits/references, capacity, encryption,
portable restore, password/tamper rejection, storage failure, stale tabs, lock
races and deletion. Gateway HTTP tests check static resource delivery, no-store,
framing protection and no core/workspace mutation. Native Chromium acceptance
exercises project edits, prerequisites, evidence, local files/notes, unapplied
fields, explicit chat/search consent, late responses, save failures, encrypted
resume/backup/restore, Markdown export and narrow/wide Persian layouts. All
projects, sources, files and chat responses in acceptance are synthetic.
