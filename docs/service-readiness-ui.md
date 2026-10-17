# Readiness observation in the workspace

The explicit Check service readiness button reads public GET /readyz with no-store and credentials omitted. No token is sent. Only HTTP 200 with status ready and HTTP 503 with status quarantined have recognized meanings. Malformed, conflicting, network and ten-second timeout responses leave availability unknown. Reads are single-flight and never retry; each new check replaces the old observation while pending.

This is an observation at the time of the check, not a continuously current guarantee. Page load and /livez do not establish write availability. Ready does not authenticate or authorize a caller. Quarantined explains that writes are blocked and authenticated reads may remain available. The panel neither disables nor enables workspace controls: the server remains authoritative for each operation, including races after an observation. It never resumes work, clears quarantine, retries mutations or constructs AuthorizedRequest.

Fourteen Node UI tests include exact HTTP/body pairs, credential omission, malformed JSON, duplicate clicks and abort. Real Chrome checks the quarantine message and GET-only behavior at narrow and wide widths using synthetic transport (nine checks per layout). Existing HTTP contracts cover actual server readiness. These witnesses do not prove production availability or physical Android behavior.

A_out <= A_in, evidence != authority, CT-001..020, the AuthorizedRequest boundary and separate Bootstrap/Verify remain required. Both Cargo.lock files remain pinned. No attestation or Seal is established by a health observation.
