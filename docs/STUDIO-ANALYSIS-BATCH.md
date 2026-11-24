# Reviewed deterministic analysis batches

Two operator-authenticated routes, POST /studio/api/analysis-batch/review and /run, add an actual bounded computational path. A batch contains an existing workflow Plan and one explicit operation per step. All steps must declare analysis; at most four operations, 64 KiB JSON, 12,000 code points per text, or 1,000 bounded integers per numeric operation. No implicit tool choice or fallback.

The review returns exact supplied operation inputs, dependency order, and a domain-separated SHA-256 digest of the entire batch. Run requires the same batch, digest and literal boolean consent. This digest detects edits; it is not a signed approval, proof of human preview, or a one-use token. Repeating a computation has no external effects. The operator token remains the existing service-level authorization. No multi-user access is implied.

text.metrics counts Unicode code points, UTF-8 bytes, whitespace-separated tokens and splitlines; it is not linguistic tokenization. numeric.summary computes count, sum, min/max, mean and median, with ordinary floating-point division where needed. Inputs are independent; dependency order does not yet pass prior outputs into later tools. Results are computed from supplied data, not independently validated source facts. No human acknowledgment or checkpoint is changed.

No shell, network, provider calls, arbitrary code, persistent output, browser integration or background execution. The server receives the supplied text/numbers; do not submit private data without operator trust. No-store does not control infrastructure logs. This candidate requires exact-head CI and deployment review.
