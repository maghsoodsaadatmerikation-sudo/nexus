# Local Studio execution

From a full repository checkout on Linux, with `uv` and Python 3.13 available:

```bash
uv run --project nexus-cloud --frozen python scripts/run-local-studio.py
```

Open the printed `http://127.0.0.1:8000/studio` URL. Stop with Ctrl+C. Use
`--port 0` for an automatically allocated port or `--port 8001` for another
fixed port. The launcher reserves the listening socket before spawning the
server, then checks liveness and model configuration. An occupied port cannot
be mistaken for a healthy Studio. No remote listening address is accepted.

## Credentials and restart

The default private directory is `~/.local/share/nexus-local-studio`; override
it with `--state-dir /your/private/directory`. The launcher generates an
owner-readable `api-token` file, reuses it on restart, and rejects insecure or
symlinked tokens. The startup output names the file but never prints the token.
An operator lock prevents two supervised processes from sharing this directory.
The server inherits the lock, so killing only the supervisor does not allow a
second launcher to reuse the state while its original server remains alive.
In that case stop the recorded `gateway_pid` before restarting.

To use a configured model, enter the token from that file into Studio's gateway
access field, leaving the gateway URL blank for this same-origin service.
The token is held transiently by the UI; it is not a provider API key. Do not
paste provider credentials into Studio. To rotate the gateway token, stop the
server, move the private token file to a secure location and restart. Deleting
or losing the token does not recover encrypted browser archives.

This directory stores launcher credentials and a lock, **not conversation
history**. Studio retains its existing explicit encrypted browser save and
portable backup behavior. Keep using a fixed port and browser profile to reopen
the same browser archive: changing the port changes the browser storage origin.
`--port 0` is useful for disposable runs, not stable browser history.

## Optional real model

The default is a local non-generative reflection guide. Model requests remain
disabled until a genuine Chat Completions-compatible provider is configured.
Supply these variables through your shell or private secret configuration:

| Variable | Required value |
| --- | --- |
| `NEXUS_MODEL_URL` | Exact completion endpoint, HTTPS or literal loopback HTTP |
| `NEXUS_MODEL_ID` | Actual model identifier accepted by that server |
| `NEXUS_MODEL_API_KEY` | Optional provider credential; retained only by the server |
| `NEXUS_MODEL_ADAPTER` | Optional `generic` (default) or `deepseek` |

A separately installed local model server may provide a loopback completion
endpoint without a paid provider, if the host has sufficient compute. This
launcher does not install models, download weights, provision compute, or
establish model quality. Partial or invalid provider settings fail before state
creation. Startup validates configuration only: it never contacts the provider,
sends a prompt, or reports a model as available. In Studio, check the connection,
review the exact context, and explicitly approve each real model request.

The generated private token replaces an ambient `NEXUS_STUDIO_TOKEN`. The child
receives only model configuration and minimal process settings. It does not
inherit core gateway credentials, proxy variables, Python injection settings or
external CORS origins. This standalone adapter does not connect to the Rust
constitutional core. Launch that core separately using `run-local-pilot.py` when
its authenticated stateful API is required.

## Verified scope

Real-process acceptance checks start the server on a reserved loopback socket,
fetch the integrated HTML, test restart and lock behavior, refuse an occupied
port and unsafe credentials, then terminate it. A synthetic local HTTP provider
checks explicit authentication and response forwarding with no startup contact.
These checks run in the frozen cloud-adapter suite; launcher sources and the
bundled HTML are included in its evidence input hashes and bundle.

The launcher is for local Linux operation, with the same local-machine trust
assumptions as the existing pilot launcher. It is not a public hosting setup,
Android app, account system, model quality evaluation or Stage D production
attestation. Dependency installation may need network access on the first run.
