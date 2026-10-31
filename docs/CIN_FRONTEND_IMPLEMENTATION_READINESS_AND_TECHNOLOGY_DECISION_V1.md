# CIN Frontend Implementation Readiness and Technology Decision (F-21)

**Date:** 2026-10-31  
**Status:** Technology decision and implementation contract; no frontend code or hosting change  
**Scope:** CIN dashboard only; read-only research and intelligence

## 1. Decision

Adopt a separate static frontend using React + TypeScript, Vite, and Cloudflare Pages Free as the proposed static-hosting target, subject to account/plan review and explicit deployment approval. The existing FastAPI service remains the API origin. Frontend and API are independently built and deployed.

Use Vitest + React Testing Library for component/state tests; Playwright for browser-level smoke, responsive and accessibility checks where CI runtime permits. Use CSS modules or plain CSS with design tokens. Do not introduce a paid component library.

This is preferred over server-rendered Next.js because the current product is an API-backed, read-only dashboard with no present need for SSR or user-specific server sessions. Static hosting avoids adding a second server runtime and reduces operational surface. It is preferred over embedding UI into the Render FastAPI scaffold because the deployment patch extracts and patches a bundled backend application; frontend coupling would expand backend release risk.

## 2. Proposed deployment topology (not activated)

- GitHub repository → frontend build → static asset output → Cloudflare Pages.
- Browser → existing CIN FastAPI API origin → public read-only providers.
- Browser receives only public API base URL configuration; no provider secrets or private credentials.
- API calls use HTTPS and one centralized typed client.
- Cross-origin access requires a narrow API CORS allowlist for the eventual Pages production hostname and approved preview origins. Do not use wildcard origins with credentials.
- No Worker, D1, KV, R2, Durable Object, paid add-on or new backend service is required for the first dashboard.
- Static build preview is not production deployment. Do not change DNS, Render, Cloudflare, auto-deploy settings or existing services as part of F-21.

## 3. Proposed repository layout

~~~text
frontend/
  index.html
  package.json
  package-lock.json
  tsconfig.json
  vite.config.ts
  src/
    app/ (App.tsx, routes.tsx)
    api/ (client.ts, errors.ts, contracts/)
    components/ (DataState, FreshnessLabel, ProvenanceDetails, MetricCard, ChartPanel, PageShell)
    features/ (overview, markets, screening, analysis, research, news, alerts, system-health)
    hooks/
    styles/ (tokens.css, global.css)
    test/
  public/
~~~

The layout is proposed. Create only modules needed for the first vertical slice; do not create empty placeholder screens that imply implemented features.

## 4. Dependency policy

- Keep production dependencies small and pin them through the committed lockfile.
- Initial foundation: React, React DOM, React Router, Vite and TypeScript.
- Add a chart library only after a spike confirms mobile behavior, accessibility alternatives, bundle impact and license compatibility.
- No analytics/telemetry SDK, advertising SDK, paid UI kit, cloud database SDK or authentication provider initially.
- Use npm and the lockfile for reproducible GitHub Actions builds; use a supported Node LTS and pinned action revisions.
- Review dependency updates for security advisories, license, bundle size and supply-chain impact.

## 5. Runtime configuration and API boundary

- Configure VITE_CIN_API_BASE_URL at build time. It is public configuration, not a secret.
- Validate HTTPS outside local development; fail visibly on missing/invalid configuration.
- All requests pass through one typed API client with bounded timeout, cancellation, normalized error categories and no automatic retry storm.
- Keep request/response models module-specific until a shared versioned API envelope is implemented. Do not fabricate the F-19 envelope client-side.
- Preserve unknown response fields and enum values safely; avoid lossy coercion.
- Handle 429/503 distinctly and respect Retry-After when present.
- Never put provider tokens or credentials in VITE_* variables; Vite exposes them in the browser bundle.
- Confirm exact deployed OpenAPI paths and target API revision before frontend integration; repository route docs do not prove live availability.

## 6. CORS and API prerequisites

Before browser-to-API integration, confirm deployed routes and schemas, define production/preview origins, add only approved origins to API CORS in a separately reviewed backend change, confirm OPTIONS/preflight behavior, and test browser CORS against an approved test origin. No CORS change is made in F-21.

## 7. Initial vertical slice

1. App shell, responsive navigation, theme tokens and global read-only banner.
2. API client, configuration validation and typed error handling.
3. Shared loading/empty/not-assessed/partial/stale/conflicting/unavailable/error/unknown state components.
4. Overview page using only endpoints with verified contracts and live availability.
5. Markets page with timestamped data and provider/freshness context.
6. Provenance detail disclosure and safe external source links.
7. Additional modules only after their APIs are verified.

The first slice must not present placeholder or mock data as live data. Fixtures are permitted only in development/tests and must be visibly identified.

## 8. Visual system and responsive behavior

- Dark-first visual direction may use near-black/navy surfaces with restrained cyan and violet accents; color is decorative, never the sole status channel.
- Use consistent spacing, typography, contrast, focus rings, chart labels and data density.
- Mobile first: one-column panels; bottom/collapsible navigation only after usability testing.
- At 360px CSS width, no horizontal page overflow; dense tables convert to cards or controlled horizontal scroll with a clear affordance.
- Provide textual chart summaries and tabular alternatives; keyboard focus and screen-reader status announcements are required.
- Respect reduced-motion preferences.

## 9. Security and privacy

- No login, wallet connect, account connection or order-related controls in the initial dashboard.
- No secrets in browser storage, source maps, build artifacts or client environment variables.
- Treat API strings/headlines/claim text as untrusted text; do not render arbitrary HTML.
- Restrict source links to HTTP(S) and validate destinations.
- No third-party analytics by default; avoid unnecessary localStorage.
- Define CSP/security headers and preview-origin restrictions before production release.
- No private keys, seed phrases, fund movement or trading execution.

## 10. Build and test gates

Required CI checks: npm clean install from lockfile; TypeScript typecheck; ESLint/static checks; Vitest component and API-client tests; production Vite build; tests for all shared data states and unknown enum handling; 429/503, timeout, malformed JSON, cancellation, empty/partial and stale-cache tests; no real provider calls in unit CI; browser smoke tests for navigation, mobile viewport, keyboard access and overflow; dependency and license review.

Release acceptance requires reproducible clean build, live values sourced only from API responses, independent panel health/provenance, approved browser origins, no unsupported features presented as operational, and explicit user approval before production Pages publication.

## 11. Alternatives considered

| Option | Assessment |
|---|---|
| React + TypeScript + Vite, static Pages | **Selected.** Static output, typed components, broad ecosystem, low operational burden. |
| Next.js server-rendered app | Not selected: adds server/runtime complexity without a current SSR/session requirement. |
| Streamlit | Not selected: rapid prototyping, but less suitable for a tailored responsive dashboard and independent static hosting. |
| Backend-rendered templates | Not selected: couples UI releases to the existing FastAPI/Render deployment and scaffold extraction/patch process. |
| Plain HTML/JS | Viable for a tiny prototype, less robust as modules and typed API contracts grow. |

## 12. Explicit non-actions and next task

F-21 is a technology decision/readiness increment only. No frontend directory, package manifest, UI code, dependency, API/CORS change, Cloudflare project, DNS change, Render change, deployment or paid service was created or modified.

**Next:** F-22 — create the minimal React/TypeScript/Vite frontend scaffold and CI build/typecheck tests on this feature branch, with fixture-only UI and no production deployment. Keep the first increment limited to the app shell and automated build verification.