# NEXUS Studio — opt-in image understanding gateway (API stage)

## What is implemented

An authenticated endpoint, POST /studio-api/vision, accepts one reviewed question and
one PNG or JPEG image for an operator-configured Chat Completions-compatible vision
model. It returns a text draft. This is API infrastructure only: there is no
Studio chat image picker, configured vision model, public rollout, or image-quality
evaluation yet.

The endpoint is disabled unless a valid NEXUS_MODEL_URL, NEXUS_MODEL_ID and
NEXUS_STUDIO_TOKEN are configured, the operator sets NEXUS_VISION_ENABLED=1,
and NEXUS_MODEL_ADAPTER=generic. A selected provider must separately support
image input; setting the flag does not verify it. API keys remain server-side.

## Exact request contract

Send JSON with Authorization: Bearer <NEXUS_STUDIO_TOKEN>:

    {
      "consent": true,
      "configuration_id": "<64 lowercase hex from GET /studio-api/status>",
      "prompt": "Describe the objects shown.",
      "mime_type": "image/png",
      "image_base64": "<canonical base64 bytes>",
      "max_output_tokens": 1024
    }

Consent must be JSON boolean true, not a truthy number/string. Reconfiguration
invalidates the request fingerprint with HTTP 409. A future caller/UI must
preview the specific image and question, reveal provider privacy implications,
and obtain human consent. The API checks consent and authentication but cannot
independently establish what the person actually previewed.

## Bounds and limitations

- Request JSON at most 2.1 MB; exactly one image up to 1.5 MB.
- PNG/JPEG only, with matching magic and structural markers. PNG chunk CRC is
  checked. Max 4,096 pixels each side and 8 million total pixels.
- Noncanonical base64, unsupported types, external image URLs, oversized
  images and dimensions are rejected.
- Prompt up to 4,000 characters; output budget 1–4,096 tokens.
- Shared four-request model concurrency, a 45-second deadline, bounded text
  response, no redirects, no tool calls and Cache-Control: no-store.
- The provider receives an embedded data URL, not an attacker-supplied URL.
- No raw image is written to NEXUS's project archive by this endpoint.
  The configured model provider DOES receive the image. Its own pricing,
  retention and logs still apply, as do the host's infrastructure logs.
- Image instructions are treated as untrusted model input; this is not
  guaranteed defense against prompt injection or evidence of answer accuracy.
- Format validation is not a complete image decoder or malware scanner.
- This is not verified OCR, medical image interpretation, face recognition,
  production readiness, or autonomous multimodal reasoning.

## Verification and next stage

Synthetic tests are in nexus-cloud/tests/test_studio_vision.py and cover the
authorization, image bounds, request forwarding, provider response rejection,
redirect refusal, and bounded recovery. The normal cloud-adapter CI must pass.
Actual provider integration, browser file preview/consent flow, image lifetime
management, costs, mobile QA, and public deployment remain separate work.

## Studio chat interface (follow-up)

The chat panel now contains an optional **Image** control and a disclosure-first
image review. A user selects one PNG/JPEG image and enters a bounded question.
Studio reads and previews it locally, verifies decoded dimensions and computes a
SHA-256 digest for the review. Merely selecting or previewing a file does not
send an image to a provider.

**Review image and provider** contacts only GET /studio-api/vision-status, which
returns a provider model/fingerprint or an honest unavailable state. The review
shows the same preview image, recipient, prompt, size, dimensions, and digest.
A separate unchecked checkbox explicitly approves the subsequent POST. Changing
the question, gateway or file invalidates the approval. A failed request does
not automatically retry; the provider may nevertheless have received the image.

The image binary stays transient in the browser. On a successful response,
NEXUS appends only the user question, a generic image-not-saved marker, and the
model's text response into the selected chat branch; **the binary is erased from
the in-page selection before writing the text state**. No automatic encrypted
save is performed. The image is also cleared on project switch, lock or private
erase, and any pending review/request is cancelled. Browser availability of the
image panel does not imply a configured or paid provider. The separate small
on-device text model is not a vision provider.

This remains a bounded single-image analysis flow, not continuous multimodal
conversation, image memory, validated OCR, video generation or clinical image
diagnosis. The user's separate text composer is not silently replaced by image
analysis. A message typed in that composer must be resolved separately before
the image answer is appended.

The new real Chromium acceptance script checks local preview/no upload on
selection, explicit model-provider/sha review, image absence from stored chat,
and invalidation on edits/lock. The cloud adapter's synthetic tests check
the network contract separately.

## Connection readiness and image removal controls

The Studio image panel has an explicit **Check vision connection (no image sent)**
button. It queries only the configured gateway's read-only vision status; it
never includes any selected image, question, bearer token, or model request.
The status distinguishes an unavailable gateway, an operator-disabled vision
provider, and a provider configuration reported as ready. A configured status
is **not** a real provider test or a promise of image analysis quality. The
separate **Model connection settings** button opens the existing secure
configuration controls without storing gateway credentials in the archive.

**Remove image and clear** now actively clears the selected image and question,
revokes any prior approval, and removes the preview from the page. Browser
regressions cover hidden preview rendering, no-upload status checks and local
removal. These tests are synthetic and cannot establish production-provider
readiness or permission to send private images.
