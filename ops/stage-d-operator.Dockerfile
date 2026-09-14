FROM python:3.12-slim

WORKDIR /operator
COPY ops/stage_d_operator.py /operator/stage_d_operator.py
COPY scripts/v1.1-release-readiness.sh /operator/v1.1-release-readiness.sh
RUN chmod 0755 /operator/stage_d_operator.py /operator/v1.1-release-readiness.sh \
    && mkdir -p /evidence

ENV EVIDENCE_DIR=/evidence
ENTRYPOINT ["python", "-u", "/operator/stage_d_operator.py"]
