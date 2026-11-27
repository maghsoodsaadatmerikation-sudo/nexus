# Public offline witness: reject new proxy connections after the cut

The public installability workflow could report
`public-egress-regained-unexpectedly` even when Chromium's navigation response
was served by its reviewed service worker and no outside tunnel was available.
The diagnostic counted active sockets accepted by the local test proxy. Chrome
could open replacement or incomplete CONNECT sockets after `cut()`, and those
inbound sockets entered the same accounting used to assert that tunnels were
closed. They could fail the assertion before rejection finished.

The proxy now destroys all newly accepted sockets immediately after the cut,
before registering them or parsing input. Existing sockets and upstream tunnels
are still destroyed by `cut()`. The public witness additionally requires the
successful outbound-connection count to remain unchanged after the cut.
The host allowlist and service-worker source/delivery assertions remain intact.

Three offline Node tests cover complete, partial and idle post-cut connections;
rejection of unrelated hosts without an outbound dial; and a real local TCP
tunnel that transfers a synthetic payload, closes on cut, and refuses eight
replacement connections without another outbound dial. The tests fail against
the historical proxy and pass against this revision. They contact no public
provider or application and are run before the real public Chromium witness.

```sh
node --test scripts/test-pilot12-public-egress-proxy.mjs
bash -n scripts/prepare-public-pilot-witness.sh
```

This fixes a test-harness admission race, not an application connectivity defect.
It does not establish general release readiness, model access or Android hardware
support. The real public Chromium workflow must pass on the new revision before
claiming that the public installability blocker has been removed.
