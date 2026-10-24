# ONCHANGE

A running log of checks and changes.

## 2026.10.23

### Fixed: CI failures in performance tests and k6 install

* Commit: 52d6d44
* Failure 1: `test_performance_sla_configuration` expected `create_ms == 3000`, but `FhirSLA` sets it to 4000 on purpose for CI runner headroom. Fix: updated the test to expect 4000. The source value is unchanged.
* Failure 2: The "Install k6" step failed with NO_PUBKEY because k6 rotated its signing key and the manual gpg import was outdated. Fix: replaced the manual steps with `grafana/setup-k6-action@v1`.
* Result: CI passed.
* Lesson: When a threshold is changed in source code, update the test that checks it in the same commit.
