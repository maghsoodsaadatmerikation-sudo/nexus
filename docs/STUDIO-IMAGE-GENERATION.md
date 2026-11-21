# NEXUS Studio — reviewed image generation API (source candidate)

**Status:** API source only; operator-disabled by default. No image provider, subscription,
server deployment, safety review or public release is implied.
Studio now includes a chat-adjacent image-generation review panel (source candidate),
not local image synthesis or a deployed image service.

## What is implemented

- `GET /studio-api/image-generation-status` reports only whether a separately
  configured compatible image-generation endpoint is available. It returns a
  configuration fingerprint and provider hostname, not credentials.
- `POST /studio-api/generate-image` accepts one explicitly reviewed text prompt,
  one of three output sizes and one signed-off `configuration_id`. A separate
  `NEXUS_STUDIO_TOKEN` Bearer credential must match the operator's token.
- The cloud adapter sends a single `n=1` request to an operator-configured
  HTTPS **Images Generations-compatible API** and accepts only a canonical,
  bounded PNG or JPEG carried in `data[0].b64_json`. It will never fetch a
  provider-returned URL, follow redirects, run model-suggested tools or write
  an output file.
- All bodies, response bytes, image dimensions, process attempts and concurrent
  requests are bounded. Provider configuration is frozen for the request;
  key rotation changes the fingerprint and invalidates prior review.
- Prompts and images are not stored by this adapter. **The image provider may
  retain them** under its own policies. The returned image belongs only to the
  requesting browser/client until explicitly saved elsewhere.

The API validates that `consent` is exactly boolean `true`; it does not prove a
human really reviewed a screen. Studio's companion UI displays an exact provider,
prompt and size review before the user checks consent and invokes this endpoint;
all calls and final download remain explicitly user-triggered.

## Operator configuration

Define these as server-side secrets/settings **outside the repo**:

| Variable | Meaning |
| --- | --- |
| `NEXUS_IMAGE_ENABLED=1` | Explicit opt-in; otherwise always unavailable |
| `NEXUS_IMAGE_URL` | HTTPS URL ending in `/images/generations`, no user info, query or fragment |
| `NEXUS_IMAGE_MODEL` | An exact provider-supported model ID |
| `NEXUS_IMAGE_WIRE_FORMAT` | `gpt` (default: modern images API) or `legacy` (older b64_json-compatible provider) |
| `NEXUS_IMAGE_API_KEY` | Separate provider credential, at least 8 characters, never exposed to clients |
| `NEXUS_STUDIO_TOKEN` | Separate Studio access credential, at least 32 characters |
| `NEXUS_IMAGE_MAX_REQUESTS_PER_PROCESS` | Required integer from 1 to 1000 |

The default modern `gpt` mode sends `{model, prompt, size, n:1, output_format:"png"}`;
modern GPT Image APIs return base64 image data without `response_format`.
The explicit `legacy` mode instead requests `response_format:"b64_json"` for
older compatible endpoints. Both require `data` with exactly one `b64_json` image.
See the [current Images API schema](https://developers.openai.com/api/reference/resources/images/methods/generate).
Provider-specific compatibility must be verified before enabling.

Use the status response to populate the displayed provider and reviewed
`configuration_id`; then prepare the exact prompt and size:

```json
{
  "consent": true,
  "configuration_id": "<64-char-hex-value-returned-by-status>",
  "prompt": "An original abstract landscape with green and purple light",
  "size": "1024x1024"
}
```

Send only after explicit approval with
`Authorization: Bearer <your-NEXUS-STUDIO-TOKEN>` and
`Content-Type: application/json`.

The response provides `image_base64`, `mime_type`, `model`, `authority:none`
and `storage:not-retained-by-nexus`. Displaying or downloading the image is
a separate user-facing task, not a server-side automated action.

## Chat user interface (source candidate)

The chat composer displays a **Generate image** chip and an adjacent, collapsible
panel. A user can copy the current unsent chat draft into the image prompt
without modifying the draft; choose square, landscape or portrait; check the
provider status without uploading the prompt; review the exact provider and
prompt; and separately approve one generation request. Editing the prompt,
size or gateway settings invalidates prior review. Output appears only in the
current tab with an explicit download action. Switching conversations or
clearing private state removes the in-memory result and pending approval.

The panel is **not a free or on-device generator**: it only works after a
compatible gateway has been deployed and authorized by the operator. The
provider may charge and may retain requests; the client labels those risks.
Real-provider compatibility and image quality are not verified by the
synthetic browser test.

## Free on-device image editing

An additional **Edit an image locally (free)** panel is available beside the
chat composer. It uses the browser's Canvas API (not a generative model) to
reversibly adjust brightness, contrast and saturation. It accepts a user-selected
PNG/JPEG up to 6 MB and can also copy the most recent generated image from the
same tab after the user selects **Use last generated image**. No cropping,
upscaling or face/body modification is performed; the original is untouched.

Image dimensions are bounded to 4,096 pixels per side and 8 megapixels.
The edits preserve the full frame and may be reset. The user must choose
**Download edited PNG** to export a new local copy; images, names and edits are
not added to chat history or encrypted project archives. Switching chats,
clearing private state or selecting Clear releases the in-memory bitmap.
Canvas encoding may strip original metadata; do not rely on metadata retention.

This panel performs **no network requests** and does not need an API key.
Its pixel changes are deterministic browser filters, **not AI-powered semantic
image editing**. Browser support, image quality and real Android device
performance require separate acceptance tests. Large decodes may temporarily
use significant RAM on low-memory phones.

## Resource and security boundaries

- Request body: at most 10,000 bytes; prompt: at most 2,000 characters.
- Provider response: at most 9,000,000 bytes; decoded image: at most 6,000,000 bytes.
- Allowed output dimensions: inherited image validation, at most 4,096 px a side
  and 8 megapixels. Allowed requested canvas sizes: 1024×1024, 1024×1536,
  1536×1024.
- At most two simultaneous upstream image requests per Python worker, with a
  60-second provider deadline.
- The process quota is **not a billable or globally durable quota**. It resets
  on worker restart and scales with worker count; operators must add a provider
  spending cap, account-level quotas, abuse controls and audit monitoring
  before exposing this to a global audience.
- No model content moderation, copyright checking, deepfake policy enforcement,
  identity checks, per-account access controls, CDN, billing, storage, or image
  quality assurance is included. These are release prerequisites, not guarantees.

## Verification

```bash
cd nexus-cloud
uv run --frozen pytest -q tests/test_studio_image_generation.py
```

All tests use mock HTTP provider responses. Passing tests verifies transport
and rejection paths only; no actual image-generation quality or public
availability is established. The NEXUS constitutional rule remains unchanged:
**AI may support human judgment, not assume its authority.**
