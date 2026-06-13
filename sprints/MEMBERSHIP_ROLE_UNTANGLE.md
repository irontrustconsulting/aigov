# Sprint hand-off — `membership.role` Untangle & Governance Enforcement

**Prerequisite (already done):** the governance-role core from `role_management.md` — `governance_role`, `governance_role_conflict`, `governance_role_assignment`, the SoD function, and the admin assignment endpoints all exist and pass. This sprint depends on them.

**What this sprint does:** make `membership.role` purely administrative, move the governance-flavoured values out of it, and make governance roles gate actions for the first time. This is the only sprint that edits existing endpoints.

---

## Goal

`membership.role` ends as `admin` / `member` only. `contributor` and `auditor` leave the enum and exist only as governance roles in `governance_role_assignment`. Every `require_role` call site is reclassified into administrative (stays on `require_role`) or governance (moves to a new `require_governance_role`). `POST /v1/systems` becomes the first endpoint gated by a governance role (`system_owner`).

---

## Work items

**1. Collapse the `UserRole` enum to `admin` / `member`.**
Write an Alembic revision chained off the core's head. Postgres cannot drop a value from an enum in place — do the type swap (create the new enum, `ALTER COLUMN role TYPE … USING …`, drop the old type) or convert the column to text with a `CHECK`. End state: only `admin` and `member` are valid.

**2. Migrate existing data.**
In the same revision, remap `contributor` → `member` and `auditor` → `member`. The migration must **not** grant any governance roles — remapping the administrative value is all it does.

**3. Add the `require_governance_role(*keys)` dependency.**
Mirror `require_role`'s variadic allow-list, but resolve the member's effective governance roles from `governance_role_assignment` on the RLS-scoped tenant session — DB-authoritative, never from token claims. Return 403 if the member holds none of the named roles.

**4. Reclassify every `require_role` call site.**
Produce the complete list of `require_role(` usages with a proposed classification for each — *administrative* (stays on `require_role`, now `admin`/`member`) or *governance* (moves to `require_governance_role`) — and surface that list for review **before** editing any of them. `POST /v1/systems` is governance → `require_governance_role("system_owner")`. For any site where the axis is ambiguous (e.g. who may *read* systems), raise it as an open question instead of guessing.

**5. Tests.**
- The revision applies on the core's head and its `downgrade` runs (see reversibility note).
- Administrative endpoints behave identically under `admin`/`member`.
- `POST /v1/systems`: a member without `system_owner` → 403; with it → success.
- No code or test references `contributor`/`auditor` as `UserRole` values.
- Full suite green.

---

## Constraints

- Governance authority is read from `governance_role_assignment` — never from token claims or `membership.role`.
- No behavioural change on administrative endpoints.
- Do not edit any call site until the classification from item 4 has been reviewed.
- The revision chains off the core's head and defines a working `downgrade`.

## Acceptance

- `UserRole` is exactly `{admin, member}`; legacy rows migrated; the app boots.
- Every `require_role` site is correctly classified; `POST /v1/systems` is gated by `system_owner`.
- Governance roles gate actions only via `require_governance_role`.
- Full test suite passes.

## Notes

- **`downgrade` is lossy by design.** It restores the `{admin, contributor, auditor}` type, but rows remapped to `member` cannot be split back into their original `contributor`/`auditor` values. State this in the revision; do not pretend it round-trips.
- **Scope:** this sprint changes authorisation gates only. It does not build the registration/classification workflow behind `/v1/systems` — that is the downstream assessment sprint.

---

## For Herbert — after the sprint (not an agent task)

- In the design-partner tenant, any user who was `contributor` or `auditor` and still needs governance capability must be granted the matching governance role explicitly, via the assignment endpoint. Negligible in dev; worth a once-over in the real tenant.