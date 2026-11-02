# Public social observation candidate

This is an unmounted, read-only experimental adapter for the public hashtag timeline on mastodon.social. It requests at most 20 public posts for a fixed allowlist (bitcoin or ethereum) and reports only a count and newest timestamp within 48 hours. It does not store post text, handles or identities. A small English keyword heuristic produces low-confidence aggregate hints from text in memory only; post content is not stored or returned. Negated, ambiguous, non-English or unmatched posts are unclassified. Empty or unclassified samples are unavailable, never automatically neutral. No forecast is inferred from post volume.

The endpoint and status fields follow the [Mastodon hashtag timeline documentation](https://docs.joinmastodon.org/methods/timelines/#tag). A server may disable public previews or require authentication, and an instance's own terms, limits and public-feed policy govern use. An empty timeline does not imply neutral sentiment; a failed request is an error, not an empty successful feed. A hashtag is not proof that a post concerns the intended asset.

Before integration into the shortlist: verify the instance's terms and public access from the Render environment; define caching, request budgets and candidate identity mapping; add safe provider failure handling and a independent evaluation of the limited sentiment methodology; then validate end-to-end. This code is not registered in the application, is not a social sentiment model, and does not satisfy the mandatory shortlist social evidence gate.

