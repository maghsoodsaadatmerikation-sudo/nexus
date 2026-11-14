# Execution reliability

The local Rust pilot and optional Studio supervisor honor SIGTERM and SIGINT even
when their child ignores SIGTERM. Their steady-state child wait polls every
200 ms so a stop request reaches the existing cleanup path. Cleanup allows five
seconds for termination, escalates to SIGKILL if needed and reaps the child before
releasing the supervisor's operator lock. A cooperative child still stops normally;
an unsolicited child exit still reports failure. This does not make SIGKILL of
the supervisor graceful: the inherited lock remains with a surviving child.

`python3 scripts/test-launcher-shutdown.py` exercises twelve cases across both
launchers: cooperative/resistant real children with SIGTERM/SIGINT and unsolicited
zero/nonzero child exits. It substitutes
readiness adapters to isolate shutdown, checks the child actually exited, checks
that the operator lock can be reacquired and checks credentials stay out of output.
Existing local-pilot and Studio suites cover real HTTP startup, persistence and
configuration separately.

The Docker build fetches locked Cargo dependencies in a layer before browser
assets are copied. It uses HTTP/1.1, a 30-second HTTP timeout and three native Cargo
network retries for the fetch. The subsequent release build uses `--frozen`, which
requires the locked dependency set and forbids Cargo network access. A first build
still needs the pinned base image and dependency downloads. Missing dependencies
fail the build; no dependency version or integrity check is bypassed.

The offline workflow has two independent acceptance jobs. `offline-pilot-browser`
retains its eight-minute budget for browser acceptance. `offline-rust-bridge` gets
a separate twenty-minute budget, with a twelve-minute image-build step. It
reconstructs a fresh synthetic browser fixture at the same checked-out revision
before exercising the real disposable Rust API. No production credential or user
artifact is transferred between jobs. Both checks must pass when reviewing the
change; a successful browser job alone does not establish Rust compatibility.

This separation fixes the observed budget coupling: dependency download timeouts
previously exhausted the shared eight-minute job after browser acceptance had
already passed. Network availability can still fail dependency retrieval, but it
no longer consumes the browser acceptance job's remaining time.

Cargo references: [network configuration](https://doc.rust-lang.org/cargo/reference/config.html)
and [fetch followed by offline commands](https://doc.rust-lang.org/cargo/commands/cargo-fetch.html).
