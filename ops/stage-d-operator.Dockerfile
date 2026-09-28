FROM python:3.12-slim

WORKDIR /operator
COPY ops/stage_d_operator.py /operator/stage_d_operator.py
COPY scripts/stage-d-evidence.sh /operator/stage-d-evidence.sh
COPY scripts/v1.1-release-readiness.sh /operator/v1.1-release-readiness.sh
COPY scripts/v1.1-release-candidate.sh /operator/v1.1-release-candidate.sh
RUN chmod 0755 \
      /operator/stage_d_operator.py \
      /operator/stage-d-evidence.sh \
      /operator/v1.1-release-readiness.sh \
      /operator/v1.1-release-candidate.sh \
    && mkdir -p /evidence

ENV EVIDENCE_DIR=/evidence
ENTRYPOINT ["python", "-u", "/operator/stage_d_operator.py"]
