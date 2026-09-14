FROM rust@sha256:0ff31c9ffa641a62e48d543fb00b4960955ea375f40776f40f585b89e654cc5e AS build

WORKDIR /workspace
COPY Cargo.toml Cargo.lock ./
COPY Dockerfile ./Dockerfile
COPY src ./src
COPY artifact-05 ./artifact-05
COPY web ./web

RUN SOURCE_TREE_SHA256="$(find Cargo.toml Cargo.lock Dockerfile src artifact-05 web -type f ! -path '*/target/*' -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')" \
    && test -n "$SOURCE_TREE_SHA256" \
    && echo "NEXUS build source tree: $SOURCE_TREE_SHA256" \
    && NEXUS_SOURCE_TREE_SHA256="$SOURCE_TREE_SHA256" cargo build --manifest-path artifact-05/Cargo.toml --release --locked \
    && test -x artifact-05/target/release/nexus-artifact-05-gateway

FROM rust@sha256:0ff31c9ffa641a62e48d543fb00b4960955ea375f40776f40f585b89e654cc5e

RUN useradd --create-home --uid 10001 nexus \
    && mkdir -p /data \
    && chown nexus:nexus /data \
    && printf '%s\n' \
      '#!/bin/sh' \
      'set -eu' \
      'chown nexus:nexus /data' \
      'exec su -s /bin/sh nexus -c "exec /usr/local/bin/nexus"' \
      > /usr/local/bin/nexus-entrypoint \
    && chmod 0755 /usr/local/bin/nexus-entrypoint

COPY --from=build /workspace/artifact-05/target/release/nexus-artifact-05-gateway /usr/local/bin/nexus

USER root
WORKDIR /home/nexus
ENV NEXUS_DATA_DIR=/data
ENV NEXUS_BIND_ADDR=0.0.0.0:3000
EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=2s --retries=3 \
  CMD bash -ec 'exec 3<>/dev/tcp/127.0.0.1/3000; printf "GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n" >&3; grep -q "200 OK" <&3'

ENTRYPOINT ["/usr/local/bin/nexus-entrypoint"]
