# Acceptance rules

This candidate campaign evaluates the missing-toolchain safe-stop behavior in
the `trial` environment. The two production version 1 cases remain historical
imported evidence, but they are not represented as regression results for this
changed bundle. A supervised production qualification would require a separate
multi-case campaign.

Each `case_sha256` binds the exact bytes of its case file. A required case must
have a receipt under the current environment-specific bundle digest with an
overall pass verdict and complete passing assertions.

<!-- acceptance:begin -->
{"case_id": "239", "environment": "production", "case_sha256": "b8c59f10fd4e9eeed8bbf18ee7ffad01bd8152d107a3ba1e75a69d4573fdba56", "required": false}
{"case_id": "240", "environment": "production", "case_sha256": "55e1315a8d95faff187c51a850fd6502f0506e55d858ae073e68d473d23e57b4", "required": false}
{"case_id": "toolchain-unavailable", "environment": "trial", "case_sha256": "0be77cca1f54bb9b3a3f1b8892d319d2dea7cd98cedbcf5d516ea488c4e84a7d", "required": true}
<!-- acceptance:end -->
