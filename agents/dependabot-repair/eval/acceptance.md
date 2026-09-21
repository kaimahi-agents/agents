# Acceptance rules

This agent's evaluation campaign currently requires the two production
version 1 cases imported from the fresh, authorized Dependabot
remediation run dated 2026-09-17. Both are historical, imported evidence
bound to the `production` environment: acceptance requires a matching,
passing receipt rendered against the current `production` bundle
digest for each. Each case's `case_sha256` binds the exact bytes of its
`eval/cases/<case_id>.yaml` file, so tampering with either case is
caught even though `eval/cases/` itself is not a bundle-digest input.

<!-- acceptance:begin -->
{"case_id": "239", "environment": "production", "case_sha256": "b8c59f10fd4e9eeed8bbf18ee7ffad01bd8152d107a3ba1e75a69d4573fdba56", "required": true}
{"case_id": "240", "environment": "production", "case_sha256": "55e1315a8d95faff187c51a850fd6502f0506e55d858ae073e68d473d23e57b4", "required": true}
<!-- acceptance:end -->
