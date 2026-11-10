# Hermes Agent patches

Local Hermes Agent adaptations live here as ordered `*.patch` files. See the
repository root README section 补丁模型 for purpose, behavior and verification.

- `0001-dual-stack-oauth-callback.patch`: bind the OAuth loopback callback on
  IPv4 and IPv6 and stop stale Windows listeners from stealing the callback.
- `0002-windows-system-proxy-fallback.patch`: fall back to the Windows per-user
  system proxy when no proxy environment variable is set.

Apply the files in filename order with `scripts/apply-patches.cmd`; do not edit
the submodule and commit those edits in the superproject.
