# NEXUS Studio — portable manual workflow checkpoints

NEXUS already offers a reviewed `/plan` checklist of two to six slash commands.
This feature adds opt-in local workflow progress export and import.

- **Download checkpoint** requests a separate confirmation that the JSON is plaintext, unencrypted, and contains the exact entered commands. No automatic download or network call.
- The strict record has only `schema`, `authority: "none"`, `verified: false`, `plan`, and a bounded integer `completed`. Completion is self-reported; NEXUS did **not** verify remote tool actions.
- **Restore workflow** reads a user-selected JSON file (maximum 4 KiB) without uploading it. It rejects extra fields, wrong schema, unsupported commands, invalid counts, unsupported extensions, and oversized files.
- A separate user confirmation is required before replacing an unsent chat draft. After a successful import, any previously opened tool step must be opened again; import grants no tool execution permission.
- Imports are bound to the current conversation and original draft; edits, project switches, archive actions and private clear invalidate pending reads. All imported instructions remain untrusted review-only content.
- English interface default, Persian prompts supported.

## Testing

```sh
python3 scripts/build-studio.py --check
python3 scripts/build-studio-static.py --check
python3 scripts/test-studio-browser.py
```

Draft-only: release is blocked pending exact-head CI and review. No production mutation, provider call, source publication or third-party audit is implied.
