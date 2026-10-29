# CIN Authorized Social-Source Ingestion Policy

## Status and purpose

This document defines the authorization and data-quality boundary for any future CIN social-source connector. It is a design specification only. No X, Reddit, or Telegram connector, credential, crawler, or message delivery is enabled by this document.

CIN must distinguish social-platform observations from public news headlines. A social post is not automatically true, representative, independent, or attributable to a real-world entity.

## Mandatory authorization gate

A connector may ingest only data that is available through an official platform API or another explicitly authorized interface, under the account's applicable permissions and current platform terms. Before enabling a provider, CIN must document:

- The exact API/product and current access tier.
- Whether the data is public, account-authorized, or explicitly user-submitted.
- The required scopes and the minimum permissions requested.
- Applicable rate limits, retention/deletion requirements, and redistribution restrictions.
- Whether the account owner has authorized the connected account and selected sources.
- A kill switch and a way to revoke credentials and stop collection.

No credential or connector may be activated until the account owner has explicitly approved the provider, scope, and collection purpose.

## Provider-specific boundaries

### X

- Use only an official, currently authorized X API product or user-provided exports with clear rights to process them.
- Do not scrape logged-in pages, bypass access controls, rotate identities to evade limits, or infer access from a public profile URL.
- Record the API product/access tier, endpoint, request time, returned post ID, author identifier only where permitted and necessary, and provider-provided timestamps.
- Treat engagement counts as time-varying provider snapshots, not unique audience or truth indicators.

### Reddit

- Use the official Reddit API or another explicitly permitted interface under current Reddit terms and applicable developer requirements.
- Respect subreddit rules, API rate limits, deletion signals, and content/retention restrictions.
- Do not treat subreddit membership or moderator status as source verification.
- Preserve subreddit/post identifiers and provider timestamps where permitted; minimize author-level data.

### Telegram

- Use only a bot or API access path explicitly authorized by the relevant account owner and permitted for the target chat/channel.
- Public channel visibility alone does not grant permission to join, scrape, archive, or redistribute content.
- Do not ingest private groups, direct messages, or restricted channels without explicit authorization from the appropriate owner and all required permissions.
- Never send messages, join channels, or manage Telegram accounts as a side effect of read-only ingestion.

## Common ingestion contract

Each accepted observation should preserve, where the provider permits:

- `provider`, `provider_product`, `endpoint_or_collection`, and `access_mode`.
- `provider_record_id`, canonical content URL, and content type.
- `provider_created_at`, `provider_updated_at` (if supplied), and CIN `retrieved_at`, all timezone-aware.
- Source/community identifier, language metadata, and the minimum permitted author metadata.
- Raw-content hash for integrity checking only where retention and platform terms allow; a hash is not proof of authorship or truth.
- Collection authorization reference, requested scopes, and policy/version identifier.
- Moderation/deletion/availability status when the provider exposes it.

Do not silently substitute CIN retrieval time for provider creation time. Missing or malformed timestamps must remain explicitly unknown.

## Evidence and sentiment rules

- Keep posts, reposts, comments, and news articles as distinct evidence types.
- Deduplicate by provider record ID first, then canonical URL where applicable; do not collapse separate user commentary solely because text matches.
- Label reposts/quotes and bot-like or coordinated activity as uncertain unless validated by a documented method.
- Do not infer real-world identity, wallet ownership, insider status, or whale attribution from usernames or social claims.
- Any sentiment score must identify language, model/lexicon version, content window, sample size, excluded content, and confidence limitations.
- Do not treat engagement volume, repost counts, or a small convenience sample as representative market sentiment.
- Cross-source agreement does not prove independent ownership or corroboration.

## Privacy, security, and operations

- Collect the minimum data needed for the approved research purpose; avoid sensitive personal data and unnecessary author profiling.
- Respect deletion, correction, retention, and redistribution obligations imposed by providers and applicable law.
- Store secrets only in an approved secret manager/environment configuration; never commit tokens, cookies, session data, or private keys.
- Redact credentials and sensitive identifiers from logs. Apply bounded response sizes, timeouts, retries, and provider-specific rate limits.
- Use read-only scopes wherever available. No trade execution, wallet control, funds movement, or outbound social messaging is part of this capability.
- Provider outages, access revocation, rate limits, stale records, and partial responses must be visible as explicit data-quality states.

## Release checklist

A provider connector is not accepted until it has: documented authorization and access tier; least-privilege scopes; provider-specific terms/retention review; deterministic parsing and schema validation; deduplication and timestamp provenance; deletion/retention handling; rate-limit and outage tests; secret/logging review; source-quality warnings; and offline tests plus separately authorized live smoke tests.

This specification is not legal advice and does not imply that any provider currently grants CIN access.
