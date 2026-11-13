# Reviewed local task runtime

Studio now runs a bounded dependency graph of JavaScript jobs, independently
of the conversational request lifecycle. Load the example in **Parallel local
tasks**, review its code and inputs, approve once, and run. The sample actually
computes a sum and count in separate workers and passes their results to a mean
job. Typing a chat message does not cancel a task plan.

The plan schema is `{version: 1, concurrency: 1 | 2, jobs: [...]}`. Each job has a
unique ASCII identifier, JavaScript function body `code`, optional string `input`
and optional array of prerequisite IDs `needs`. No unknown fields, duplicate
IDs, missing prerequisites or cycles are accepted. Maximum 12 jobs, 512 KiB
serialized plan, 100,000 bytes of code and 128 KiB direct input per job.

Each job receives the string `input`, containing JSON with its direct `input`
and a `dependencies` map. Dependency values are **result strings**, not executed
code. Results are untrusted, inert text. The complete envelope is bounded to
256 KiB and each result to 64,000 bytes. Console output is bounded by the existing
sandbox but is not retained by this scheduler.

Ready jobs run on at most two separate opaque-origin browser sandboxes. Each
sandbox uses a dedicated worker, denies network and archive access, and has a
3-second execution watchdog plus a 6-second startup deadline. A failed job blocks
its descendants; independent work continues. Cancel stops running and queued
work. A 60-second plan watchdog terminates unfinished jobs. There is no hard
memory quota; closing the tab or browser may lose all work.

Plans and reports are temporary. Editing a plan revokes approval and cancels its
workers. Changing projects, replacing an archive, or locking clears them. Reports
can be explicitly exported; they are never inserted into conversations, sources
or model context automatically. No provider credentials are used.

## Boundaries against the requested DeepSeek feature list

| Requested property | Implementation status |
| --- | --- |
| Asynchronous routing and isolated concurrent workers | Implemented as the bounded local scheduler above, with failure propagation and watchdogs |
| Worker subtasks | Explicit reviewed dependency graph; no autonomous worker spawning |
| Persistent multi-channel router, durable server jobs | Not implemented by this browser runtime |
| Self-feedback RL and benchmark parity | Require actual training/evaluation; not claimed |
| Thinking/non-thinking, vision, 1M context | Depend on a real configured model and its API contract; not added by this change |
| Search and fetch | Existing explicit Wikipedia/Crossref research desk; not unrestricted search or a DeepSeek Search/Fetch adapter |
| MoE / MLA / DSA / IDSA / CSA / HCA | Model/inference-engine architectures; this application scheduler does not implement or simulate them |
| GPU/NPU open-weight serving | Requires weights, serving engine, hardware and deployment; no provisioned accelerator |
| Token prices or training cost | No invented price or token accounting; provider billing remains external |

Validation: deterministic bundle; scheduler contract tests for real scheduling
ordering, concurrency, validation, result bounds, cancellation and failure
propagation; Chromium lab witness extended to exercise actual workers, dependency
computation, chat independence, infinite-loop termination, network sentinel and
project/lock cleanup. A passing Node contract test does not establish browser
sandbox isolation; the Chromium witness is separately required.

## Optional DeepSeek Chat Completions adapter

The Python model gateway additionally supports `NEXUS_MODEL_ADAPTER=deepseek`.
The operator must choose an endpoint and model that actually support DeepSeek's
Chat Completions `thinking` contract; credentials remain server-side. The default
`generic` adapter keeps the existing wire contract and rejects non-default modes.
Unknown adapter names disable configuration. Switching adapter changes the
configuration fingerprint and invalidates already-reviewed requests.

Studio exposes provider-default, thinking and non-thinking modes plus a bounded
1–8192 generated-token limit. The review includes both settings. Changing them
revokes approval. For the DeepSeek adapter, explicit thinking/non-thinking sends
`thinking.type=enabled/disabled` and uses `max_tokens`; the generic adapter uses
`max_completion_tokens`. This is a provider capability, not local model training.
The existing 45-second gateway deadline, 128,000-byte response cap and 24,000
character final-answer cap remain enforced; larger token budgets may time out or
hit these limits. Reasoning text is not returned to Studio. No provider has been
provisioned or activated by this source change, and there is no live-model test.

Primary API reference: https://api-docs.deepseek.com/guides/thinking_mode/
Model architecture reference: https://github.com/deepseek-ai/DeepSeek-V3
