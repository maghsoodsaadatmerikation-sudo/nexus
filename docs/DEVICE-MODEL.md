# Optional device model

Studio can optionally load **HuggingFaceTB/SmolLM2-135M-Instruct**, q8, using
Transformers.js 4.3.2 and a single-threaded WASM Worker. This is a small English
drafting model with limited accuracy, not a replacement for a large hosted model.
No account, provider API key, hosted inference service or paid instance is added.

## Explicit download and review

1. Open the device-model panel and review the roughly 167 MB initial download.
2. Select download consent and choose **Load small model**. The controls refuse
   a missing consent or a browser without Worker/WASM/Cache/crypto support.
   Browsers reporting less than 4 GB device memory are refused before download.
3. Select **On-device small model** under model settings. The existing remote
   gateway remains a separate choice; there is no silent remote fallback.
4. Prepare the request. The preview includes the fixed local policy, exact
   selected messages, model identity, input cap and output budget. Project memory
   and source excerpts retain their existing opt-ins.
5. Approve that exact request. The model receives it inside the device Worker.
   The resulting conversation entry explicitly identifies an on-device draft.

The model, revision and runtime artifact sizes/digests are locked in
`web/device/model-manifest.json`. The remote model/runtime download is
167,471,893 bytes; small reviewed local JS modules are additional. Downloads
contact Hugging Face and jsDelivr, which can observe ordinary request metadata
such as IP address and selected artifact. Conversation text is not placed in
artifact URLs, headers or caches. Runtime and model files are checked for exact
size and SHA-256 before use or reuse. Only fixed public artifacts may be fetched;
network fetches are disabled during generation. Model weights are not in Git or
on the static site's repository-backed asset directory.

## Limits and cancellation

The maximum input is 768 tokenizer tokens, including the fixed policy. The
maximum generated output is 64 tokens. A preliminary 6,000-character message-JSON
cap bounds review/worker transfer. Oversized input is refused, never silently
summarized or truncated. The local engine supports standard deterministic
inference only; remote thinking modes remain unchanged.

Loading has a five-minute deadline, each remote artifact request has a three-
minute deadline, and generation has a two-minute deadline. Stop/abort terminates
the local Worker; this actually stops this local computation. A changed draft,
selection or context invalidates a prepared request and late results are
ignored. Lock unloads the model. Reloading after a stop requires explicit load
consent again; already verified public files can be reused from cache.

The runtime/model cache is `nexus-device-artifacts-v1`. Erasing it unloads the
model and removes only those public files. It does not erase Studio's encrypted
history or app-shell cache. Removing the offline app copy likewise leaves the
separate model cache alone. Save conversations explicitly and keep an encrypted
portable backup independently.

The app-shell cache now contains the index and four integrity-pinned local
module/worker/manifest files so the optional controls remain usable offline.
The model's vendor code and weights are cached separately only after explicit
model-load consent. Offline model reuse still depends on those complete caches,
browser storage retention and compatible hardware.

## Verification scope

`device-model.yml` runs a real pinned-weights WASM inference witness in a fresh
headless Chromium profile, plus a synthetic Studio transport witness for consent,
policy review, provenance, late-response rejection and lock behavior. The real
witness checks an English answer grounded in an explicitly supplied fact, capacity rejection, cancellation and
scoped cache removal. This is an execution smoke check, not a general quality,
medical accuracy, alignment or multilingual evaluation. Physical Android speed,
memory and reliability need device acceptance; a successful desktop browser
witness does not establish them.

Primary upstream references:

- https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct
- https://huggingface.co/docs/transformers.js/en/custom_usage
- https://huggingface.co/docs/transformers.js/api/env
- https://github.com/huggingface/transformers.js

Downloaded Transformers.js/Jinja code is Apache-2.0/MIT as attributed in its
upstream distributions; ONNX Runtime is MIT. License texts are shipped with the
runtime. Model licensing is Apache-2.0 according to the upstream model card.

During development, an ungrounded color question produced a misleading answer
about interpretation. This model is therefore presented as limited text drafting
from supplied information, not verified independent factual question answering.
Passing the grounded execution smoke does not certify general knowledge.

## Readiness and local execution reports

**Check device readiness** makes no model request and starts no Worker. It checks
basic secure-context/Worker/WASM/cache/crypto availability, the browser's coarse
memory hint, and `navigator.storage.estimate()` when available. The storage
headroom suggestion is three times the pinned download size; it is an advisory
browser-quota estimate, not measured free RAM. Missing estimates remain unknown.
Low storage is advisory so an already cached model is not falsely blocked.
Passing these checks does not certify actual model execution or Android support.

**Download local execution report** explicitly exports an allowlisted JSON report
from this tab: current model state, configuration fingerprint, observed generation,
input/output token budget and elapsed time. It excludes input/answer text, project
names, source excerpts, passwords and access tokens. The report is not uploaded,
not saved automatically, and not an independent attestation or quality evaluation.
Lock/unload/erasure clears the in-memory observation. A model process that cannot
start, crashes or exceeds its deadline returns to a retryable idle state with a
specific non-sensitive recovery code.
