# NEXUS Studio: opt-in capability disclosure in chat

This stacked draft integrates the read-only capability registry from PR #420 into the existing chat-first composer. It does **not** introduce autonomous tools, new provider keys, or change consent rights.

Click **Tool status** or type **/readiness** in chat (also recognizes an exact English/Persian status request). This opens a panel **without a network request** and preserves the draft. Enter an operator gateway URL and Studio access token in the existing model settings, then click **Check gateway configuration (read-only)**. The action sends one bounded authenticated GET to the validated NEXUS gateway origin, with no chat text or attachments. It never executes any tool.

The strict versioned response is rendered using text-only DOM nodes; states distinguish source-defined-but-browser-unverified, configured-but-not-live-tested, not-configured, exhausted/unavailable model budget and not-implemented. Nothing is represented as executed, independently verified or production ready. Closing the panel, switching projects, clearing private data or editing gateway credentials revokes in-flight results. Errors and malicious responses fail closed, without saving results.

The existing Chromium acceptance witness adds opt-in network checks, auth, invalid-result rejection, cancellation, source-truth labels and draft preservation. Static Studio SRI/offline assets must be rebuilt from the revised chat composer before merge. No public deployment or merge is authorized. Commits use `[skip render]`.
