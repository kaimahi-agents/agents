# Acceptance rules

The fixed greeting case is required in `trial`. Until a receipt exists under the
current digest's `eval/receipts/<bundle_digest>/` directory, `tools/verify
agents/hello trial` fails with a missing-receipt diagnostic; that failure is
the expected state before a live run is recorded.

<!-- acceptance:begin -->
{"case_id": "fixed-greeting", "environment": "trial", "case_sha256": "34769787e6ecd6af5ebcd42c4e55af418737065ffc281ea698642842843d0443", "required": true}
<!-- acceptance:end -->
