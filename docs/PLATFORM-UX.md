# PLATFORM-UX.md — IronTrust Operator Console Design Intent

**Location:** `docs/PLATFORM-UX.md` — single source, mirrored to project knowledge. Updated rarely (stable spec); per-surface intent filled just-in-time.
**Purpose:** The experience intent for the **platform plane** — the operator console used by IronTrust staff. The counterpart to `UX.md`, for the other plane. Intent, not implementation.
**Lanes:** tenant-product experience → `UX.md`; *how it is rendered* → `FRONTEND.md` (when it lands); platform-plane mechanics (operator auth, RBAC, routers, DB roles) → `ARCHITECTURE.md`. **This file is platform-plane only.**

---

## 1. Founding principle — platform functionality is UI-operated

**INV-49 / D-36.** Every platform-plane capability that requires ongoing operator interaction is operated through the operator console UI. CLI/scripts are reserved for initial bootstrap and break-glass that must precede or underlie the UI — DB-role creation (`00_roles.sh`), first-operator seeding, the first tenant before any console exists. A platform feature that needs interactive operation is **not done until its operator UI is built**: the UI ships with the feature, never as a deferred follow-on.

This refines D-23 — UI is the primary operator surface; the provisioning CLI persists only as the bootstrap/break-glass path. The boundary: ongoing interactive operation → UI; one-time environment bootstrap or break-glass that precedes the UI → script is acceptable.

---

## 2. Audience — the operator (platform plane)

IronTrust staff, on the platform plane (separate Cognito pool, `require_permission`, INV-1). Design drivers are the **inverse** of `UX.md`'s tenant thesis: expert users who *are* the compliance/ops experts; efficiency and information density over friendliness; operational vocabulary; no adoption dynamic and no reveal-compliance-on-demand layering. Operator authority is permission-gated through roles only (INV-8); every operational act is attributable on the platform audit plane (`PlatformAuditEvent`).

**Plane separation is a UX rule.** Operator and tenant surfaces never bleed: an operator never appears inside a tenant governance surface, and the operator console never renders a tenant-plane face. The visual/interaction correlate of INV-1.

---

## 3. Surfaces (fill-as-you-go)

Designed just-in-time when built, each run through §1–2 and INV-49. The framework to fill:

- **Provisioning console** — create / list tenants; wraps `provision_tenant` / `POST /platform/provision` (D-23). CLI remains the bootstrap path only. *[to design when built]*
- **Operator RBAC** — operators, roles, role→permission grants (INV-8); operator status. *[to design when built]*
- **Catalogue & reference curation** — vendors / products / facts / mappings, risk & control libraries, taxonomy, decision tree (the GLOBAL reference data, INV-48). *[to design when built]*
- **Curation-task inbox** — the tenant-side taxonomy misses routed here (`UX.md` §3); the operator adds the option properly, with its mapping, and it becomes structured for everyone next time. The moat-compounding loop. *[to design when built]*

---

## 4. Implementation conventions — elsewhere

Rendering (components, design tokens, typography, accessibility, framework) → `FRONTEND.md` when it lands. This file is intent; that is implementation. When a surface is built, it honours this document and follows those conventions.