FROM rust@sha256:0ff31c9ffa641a62e48d543fb00b4960955ea375f40776f40f585b89e654cc5e AS build

WORKDIR /workspace
COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY artifact-05 ./artifact-05
COPY web ./web

RUN cargo build --manifest-path artifact-05/Cargo.toml --release --locked \
    && test -x artifact-05/target/release/nexus-artifact-05-gateway

FROM rust@sha256:0ff31c9ffa641a62e48d543fb00b4960955ea375f40776f40f585b89e654cc5e

RUN useradd --create-home --uid 10001 nexus \
    && mkdir -p /data \
    && chown nexus:nexus /data

COPY --from=build /workspace/artifact-05/target/release/nexus-artifact-05-gateway /usr/local/bin/nexus

USER nexus
WORKDIR /home/nexus
ENV NEXUS_DATA_DIR=/data
ENV NEXUS_BIND_ADDR=0.0.0.0:3000
EXPOSE 3000

ENTRYPOINT ["/usr/local/bin/nexus"]
