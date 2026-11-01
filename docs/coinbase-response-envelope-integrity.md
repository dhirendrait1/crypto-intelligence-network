# Step 195 — Coinbase successful response-envelope integrity

Coinbase's public product-catalogue and candle endpoints are expected to return top-level JSON arrays on successful responses. The adapter now enforces that envelope at the shared Coinbase JSON request boundary, before endpoint-specific catalogue or candle-row processing.

A successful HTTP response containing a JSON object (including an error-shaped object), scalar, string, or null is malformed provider data. It is not treated as a valid empty result, a retryable outage, or permission to silently fall back to another provider. Invalid JSON and decoding failures remain classified as malformed successful response bodies.

An empty top-level array is structurally valid at the envelope layer. Endpoint-specific logic remains responsible for deciding whether an empty catalogue or empty candle result is usable; this step does not conflate envelope validity with business-level completeness.

Offline regression tests cover valid non-empty and empty arrays, object/error-shaped envelopes, null and scalar JSON values, invalid JSON, and the fail-closed classification boundary. The tests do not make live Coinbase requests and do not establish future provider compatibility.

No row ordering, timestamp, pagination, candle-value, fallback-policy, or public API schema behavior is changed. No data is repaired or synthesized. CIN remains strictly read-only: no order execution, wallet access, merge, Render deployment, or production activation.
