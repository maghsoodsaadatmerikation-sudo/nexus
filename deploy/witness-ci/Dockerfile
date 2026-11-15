# CI-only fixture: real OpenSSH TCP across isolated Docker namespaces.
# NOT an operator deployment image or an independently approved base image.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    ca-certificates openssh-server openssh-client openssl python3 \
    util-linux coreutils passwd \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/sh witness \
    && passwd -d witness \
    && mkdir -p /opt/nexus-witness /run/sshd /etc/ssh/keys
COPY --chown=root:root scripts/workspace-attestation.py \
    scripts/workspace-trust.py \
    scripts/workspace-offsite-witness.py \
    scripts/workspace-witness-custodian.py \
    scripts/workspace-witness-recovery.py \
    scripts/workspace-witness-host.py \
    scripts/workspace-witness-ssh-client.py \
    /opt/nexus-witness/
RUN chmod 0755 /opt/nexus-witness && \
    chmod 0644 /opt/nexus-witness/*.py
CMD ["sleep", "infinity"]
