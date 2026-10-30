# CIN Step 23 — Access Control and Authorization Readiness v1

**Status:** Security boundary review and design proposal only. No authentication, roles, permissions, or production access-control system is activated by this document.  
**Current boundary:** Public evidence ingestion is read-only; injected EvidenceStore dependency is unused; SQLite adapter is local-only and caller-owned.

## 1. Executive finding

The reviewed Step 23 API and storage code define a useful separation between the read-only provider route, the EvidenceStore protocol, and the explicit local SQLite adapter. However, the reviewed files do not implement authenticated identities, authorization roles, scoped permissions, database access controls, export authorization, retention-operation authorization, or an audit trail for privileged actions.

The SQLite schema has no user, role, permission, tenant, or authorization tables. The adapter accepts a caller-supplied connection and does not authenticate its caller. The FastAPI endpoint validates request fields and source allowlists but does not authenticate a user. Its optional store dependency is not used to write data.

This is a repository-level finding; it does not assess hosting-provider account security or GitHub repository permissions.

## 2. Current trust boundaries

| Boundary | Current behavior | Security interpretation |
|---|---|---|
| Public API caller | Request validation; ETH and repository allowlist | Input validation is not caller authentication |
| API route | Read-only provider fetch; generic 502 errors | No persistence authorization is currently exercised |
| Store dependency | Returns only explicitly configured app-state store or None | Dependency injection is not access control |
| EvidenceStore protocol | Defines append/read operations | Contract does not enforce caller identity or permissions |
| Local SQLite adapter | Explicit connection; local reference only | Connection possession is effectively authority; no row-level roles |
| Migration/schema | Foreign keys, checks, append-only triggers | Integrity controls are not authentication or authorization |
| Export/backup/restore | No governed operational workflow evidenced | No authorization boundary is implemented |
| Retention/erasure | Design only; no worker or operation | No deletion authority or privileged workflow exists |

## 3. Required future authorization model

Before any write-capable API or persistent service is enabled, define and review:

- **Principal:** authenticated human, service identity, or automation identity; never infer identity from a request body.
- **Authentication:** trusted identity provider or securely managed service credentials; no home-grown password/token storage in the evidence database.
- **Authorization:** deny-by-default permissions checked server-side on every operation.
- **Scope:** least-privilege environment, source namespace, record set, and operation scope.
- **Separation of duties:** ingestion, assessment/review, export, retention/erasure, and restore release must not automatically share authority.
- **Audit:** append-only, payload-minimized records of privileged actions, actor/principal reference, permission/policy version, target scope, outcome, and timestamp.
- **Revocation:** defined credential/identity revocation and session invalidation behavior.
- **Break-glass:** if required, explicit scope, short duration, independent approval, alerting, and post-event review.

Suggested permission vocabulary for review (not active roles):
- `evidence.read_public`
- `evidence.ingest_candidate`
- `evidence.append_observation`
- `assessment.propose`
- `assessment.review`
- `export.request`
- `export.approve`
- `retention.dry_run`
- `retention.approve`
- `retention.execute`
- `backup.restore`
- `restore.release`
- `policy.manage`

Do not assign these permissions to roles until the project approves a role matrix and operational identity model.

## 4. Required operation controls

| Operation | Minimum authorization gate | Required independent control |
|---|---|---|
| Public metadata fetch | Public endpoint rate/abuse controls; source allowlist | No storage write implied |
| Persist evidence | Authenticated service principal plus source/policy scope | Explicit opt-in adapter and validated mapping |
| Append observation | Scoped evidence-write permission | Immutable event; provenance preserved |
| Create/modify claim | Claim-authoring permission | Versioned claim history; no evidence authenticity inference |
| Human assessment | Reviewer identity and assessment permission | Reviewer identity must be authenticated, not caller-asserted |
| Export/support bundle | Request permission and separate approval for sensitive scope | Redaction and recipient/expiry checks |
| Retention dry-run | Read-only retention-review permission | Payload-free manifest |
| Retention execution | Separate approval and narrowly scoped execution permission | Two-person or otherwise approved control; idempotent verification |
| Backup restore | Restore operator permission | Isolated restore and erasure replay |
| Restore release | Separate release permission | Must not be granted automatically to restore operator |
| Policy change | Policy manager permission with approval evidence | Immutable policy version and review record |

## 5. Fail-closed requirements

- Missing, invalid, expired, revoked, or unverifiable principal: deny.
- Missing permission or ambiguous scope: deny.
- Client-supplied role, actor ID, approval flag, or reviewer identity is never authoritative.
- Authorization service unavailable: deny privileged operations; do not fall back to permissive mode.
- A public read-only endpoint must not gain write behavior because a store is injected into app state.
- Local SQLite connection possession must not be represented as production authorization.
- Error responses must not disclose credentials, internal policy detail, record payloads, or database internals.
- Privileged audit failures must block the protected operation unless a separately approved safe mode exists.

## 6. Safe implementation sequence

1. Inventory deployed endpoints, app-state construction, secrets, GitHub permissions, Render service settings, and any external identity provider without changing them.
2. Define the principal types and threat model.
3. Approve a permission matrix and separation-of-duties model.
4. Select an existing trusted identity provider or service-auth mechanism consistent with the $0-first constraint; do not invent a paid dependency or store passwords in CIN.
5. Define a versioned authorization interface and policy decision contract.
6. Add tests for every allow/deny combination, revoked identities, wrong scope, spoofed actor fields, service outage, and audit failure.
7. Add privileged-operation audit records with minimized fields.
8. Review API exposure, rate limits, secrets handling, deployment identity, and database connection privileges.
9. Only then consider a separately approved write-capable integration or retention operation.

## 7. Acceptance tests before write or privileged operations

- Unauthenticated caller cannot invoke protected operations.
- Caller cannot elevate privilege by sending role, actor, reviewer, or approval fields.
- Principal can access only explicitly granted source/record/environment scope.
- Revoked or expired identity is denied.
- Authorization service failure is fail-closed.
- Store injection alone never enables writes through the public API.
- Read-only public fetch remains read-only under every app configuration.
- Export and retention approval cannot be performed by the same principal where separation is required.
- Restore operator cannot independently release the restored dataset.
- Audit records contain no raw evidence payload, credential, private key, seed phrase, or unnecessary personal data.
- Audit failure blocks privileged operations or follows a separately approved exception path.
- No trade, wallet, key, or fund-movement permission exists in the CIN permission vocabulary.

## 8. Unresolved decisions

| Decision | Evidence/approval required | Status |
|---|---|---|
| Human/service principal model | Threat model and explicit project decision | Not approved |
| Authentication provider/mechanism | Security review and $0-first compatibility | Not selected |
| Permission and role matrix | Least-privilege matrix and separation-of-duties approval | Not approved |
| Reviewer identity assurance | Authenticated identity and reviewer policy | Not implemented |
| Export/retention/restore authority | Named accountable authority and approval process | Not approved |
| Audit storage and integrity | Threat model, access scope, retention policy | Not designed in runtime |
| Rate limiting/abuse controls | API threat review and deployment evidence | Not established by reviewed files |
| Secret management and rotation | Deployment/account review | Not assessed here |
| Production activation | Separate explicit project approval | Not authorized |

## 9. Explicit non-actions

No authentication provider, role, permission, token, secret, database table, API write path, export mechanism, retention worker, backup, restore, or deployment configuration was created or changed. No user identity or authorization capability is inferred from the existing dependency injection. The public API remains read-only and SQLite remains a local reference adapter.

**Disposition:** Access-control requirements and repository evidence gaps are explicit. Authentication/authorization are not implemented; privileged operations remain unauthorized; Step 23 remains Partial.
