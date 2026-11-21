# NEXUS Studio — reviewed image generation API (source candidate)

**Status:** API source only; operator-disabled by default. No image provider, subscription,
server deployment, end-user Studio image composer, safety review or public release is implied.
This is a foundation for an optional user-reviewed image feature, not local image synthesis.

## What is implemented

- \`GET /studio-api/image-generation-status\` reports only whether a separately
  configured compatible image-generation endpoint is available. It returns a
  configuration fingerprint and provider hostname, not credentials.
- \`POST /studio-api/generate-image\` accepts one explicitly reviewed text prompt,
  one of three output sizes and one signed-off \`configuration_id\`. A separate
  \`NEXUS_STUDIO_TOKEN\` Bearer credential must match the operator's token.
- The cloud adapter sends a single \`n=1\` request to an operator-configured
  HTTPS **Images Generations-compatible API** and accepts only a canonical,
  bounded PNG or JPEG carried in \`data[0].b64_json\`. It will never fetch a
  provider-returned URL, follow redirects, run model-suggested tools or write
  an output file.
- All bodies, response bytes, image dimensions, process attempts and concurrent
  requests are bounded. Provider configuration is frozen for the request;
  key rotation changes the fingerprint and invalidates prior review.
- Prompts and images are not stored by this adapter. **The image provider may
  retain them** under its own policies. The returned image belongs only to the
  requesting browser/client until explicitly saved elsewhere.

The API validates that \`consent\` is exactly boolean \`true\`; it does not prove a
human really reviewed a screen. A future client needs an actual visible approval
step before invoking this endpoint.

## Operator configuration

Define these as server-side secrets/settings **outside the repo**:

| Variable | Meaning |
| --- | --- |
| \`NEXUS_IMAGE_ENABLED=1\` | Explicit opt-in; otherwise always unavailable |
| \`NEXUS_IMAGE_URL\` | HTTPS URL ending in \`/images/generations\`, no user info, query or fragment |
| \`NEXUS_IMAGE_MODEL\` | An exact provider-supported model ID |
| \`NEXUS_IMAGE_API_KEY\` | Separate provider credential, at least 8 characters, never exposed to clients |
| \`NEXUS_STUDIO_TOKEN\` | Separate Studio access credential, at least 32 characters |
| \`NEXUS_IMAGE_MAX_REQUESTS_PER_PROCESS\` | Required integer from 1 to 1000 |

The provider must accept \`{model, prompt, size, n:1, response_format:"b64_json"}\`
and return a JSON \`data\` array containing exactly one image with \`b64_json\`.
Some commercial models do **not** implement this wire format. Compatibility
must be verified against the actual selected provider before enabling.

Use the status response to populate the displayed provider and reviewed
\`configuration_id\`; then prepare the exact prompt and size:

\`\`\`json
{
  "consent": true,
  "configuration_id": "<64-char-hex-value-returned-by-status>",
  "prompt": "An original abstract landscape with green and purple light",
  "size": "1024x1024"
}
\`\`\`

Send only after explicit approval with
\`Authorization: Bearer <your-NEXUS-STUDIO-TOKEN>\` and
\`Content-Type: application/json\`.

The response provides \`image_base64\`, \`mime_type\`, \`model\`, \`authority:none\`
and \`storage:not-retained-by-nexus\`. Displaying or downloading the image is
a separate user-facing task, not a server-side automated action.

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

\`\`\`bash
cd nexus-cloud
uv run --frozen pytest -q tests/test_studio_image_generation.py
\`\`\`

All tests use mock HTTP provider responses. Passing tests verifies transport
and rejection paths only; no actual image-generation quality or public
availability is established. The NEXUS constitutional rule remains unchanged:
**AI may support human judgment, not assume its authority.**
