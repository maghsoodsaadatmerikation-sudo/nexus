# NEXUS Studio: explicit module graph and ownership boundary

The Studio standalone HTML bundle historically listed 22 JavaScript source modules
inside `scripts/build-studio.py`, while the shell contained separately maintained
placeholder slots. Runtime global dependencies were implicit. A new feature
could inadvertently access a different tool's internals, or a rearranged
script could load before a required provider.

## Implementation

The reviewed manifest `scripts/studio_module_graph.py` is now the one source
of truth for module ordering, source paths, global exports and dependencies.

- **Provider ownership:** each `Nexus*` export has one declared owner.
- **Eager dependencies:** `requires` may refer only to globals provided by
  earlier source modules.
- **Deferred dependencies:** `deferred` are explicit late references to
  approved UI modules; the device-model bridge `NexusDevice` is separately
  loaded and explicitly listed as an external optional reference.
- **Unknown coupling:** a previously undeclared `Nexus*` reference or global
  export fails the build instead of silently creating cross-tool coupling.
- **Deterministic assembly:** the existing source order and HTML output are
  preserved. No dynamic imports, network calls or new runtime privileges were
  added by this change.

The graph scanner is a conservative lexical guardrail, not a JavaScript AST
type-checker. It tracks named `Nexus*` interfaces, not general browser
globals such as `EN`, `document`, or DOM events. Tests still need to validate
runtime behavior and the non-authoritative boundary.

## Verification

`scripts/test-studio-module-graph.py` validates the real source graph and
negative cases: missing/duplicate/new slots, reordering, unknown references,
undeclared providers, forward dependencies and path traversal. The Studio
workflow executes the graph test before `build-studio.py --check`; existing
browser and static package acceptance suites remain mandatory.

This is architectural coupling control, not a refactor of every runtime
interface and not a production release authorization. The underlying Rust
constitutional authority boundary is unchanged.
