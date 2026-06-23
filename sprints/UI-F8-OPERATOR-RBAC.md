# SPRINT HANDOFF (execution-only) · `UI-F8-OPERATOR-RBAC` — Operator Management Console

**Status:** ready to execute · plane PLATFORM (operator) · durable route delta +3 · schema/migration delta 0 DDL · rationale lives in `UI-F8-OPERATOR-RBAC_design.md`, not here.

Execution-only. Work items are dependency-ordered. Done-checks are tied to concrete tests. Do not begin a code work item until §0 is cleared; V-α, V-β, V-ε are blocking pre-flight. WI-1 (seed) precedes the genesis done-check (WI-6).

---

## §0 — Pre-flight verify (clear before any code; `D-21`)

- [ ] **V-α (BLOCKING)** — platform `role`/`permission`/`role_permission` seed home and mechanism: data-seed loader (`scripts/seed/`, `data/seed/`) vs the migration that created `platform_rbac`. `INV-48` scopes the loader to GLOBAL reference data, which does not list the platform-RBAC tables, so do not assume the loader path. Confirm only `provisioner`/`tenant:provision` exist today. Outcome sets WI-1's form (seed file vs migration revision); "0 DDL" holds either way.
- [ ] **V-β (BLOCKING)** — fix the byte-exact new permission literal (`operator:create` proposed); confirm `platform_admin` is a free role key; confirm **no pre-existing `operator:*` permission and no third operator-management role** (WI-2's shared gate depends on it); decide the API-ROUTES gate-column annotation so it does not render `operator:operator:create`.
- [ ] **V-ε (BLOCKING)** — confirm `provision_operator` creates a login-capable operator-pool Cognito user + invite (not just a DB row), and the operator-pool app-client/invite flow is wired. Gates WI-6.
- [ ] **V-γ** — `provision_operator` signature/return/exceptions (from `admin.py`); whether it stages a `PlatformAuditEvent` on the HTTP source; `actor=None` handling; the exact `source=` literal `POST /platform/provision` passes (`tenants.py` shows `"http"`), to be matched, not reinvented.
- [ ] **V-δ** — `Operator` (`status`/`OperatorStatus` labels), `operator_role`, `role` fields for the list; confirm no `GET /platform/operators` exists.

---

## WI-1 — Seed `platform_admin` + `operator:create` + grants (backend; precedes WI-6)

Depends on V-α, V-β.

- Via the mechanism V-α identifies (seed file or migration revision; not a parallel path): add permission `operator:create`; add role `platform_admin`; add `role_permission` grants: `platform_admin` → **all** permissions (`tenant:provision`, `operator:create`, and any others present); `provisioner` unchanged.
- No DDL.

**Done-check:** after seed, `platform_admin` resolves to the full permission set via the `Operator → OperatorRole → Role → RolePermission → Permission` chain; `provisioner` resolves to `{tenant:provision}` only; `operator:create` exists exactly once.

## WI-2 — `POST /platform/operators` (backend)

Depends on WI-1, V-γ.

- Wrap `provision_operator(email, display_name, role_key, actor=<calling operator>, source=<V-γ literal>)`. Gate `require_permission("operator:create")`.
- Error mapping: `OperatorAlreadyExists` → 409; `RoleNotFound` → 422; `OperatorProvisioningError` → **500** (matches `members.py::create_member`).
- Response `{operator_id, cognito_sub}`. Schemas `OperatorCreate`/`OperatorCreated` in `app/schemas/platform.py`.

**Done-check** (`tests/platform/test_operators_create.py`): `platform_admin` creates a `provisioner` → 201, invite asserted; duplicate email → 409; unknown role → 422; `provisioner`-only caller → 403; a created `PlatformAuditEvent` attributes the calling operator (per V-γ outcome).

## WI-3 — `GET /platform/operators` + `GET /platform/roles` (backend)

Depends on WI-1, V-δ. Both gate `require_permission("operator:create")` (DF7-1 shared gate).

- `GET /platform/operators` → `list[OperatorListItem]` (id, email, display_name, status, roles).
- `GET /platform/roles` → `list[RoleListItem]` (key, display label) for the form select.

**Done-check** (`tests/platform/test_operators_list.py`): `platform_admin` → 200 with the genesis operator present and its role; `provisioner`-only → 403; roles list returns `provisioner` and `platform_admin`.

## WI-4 — Operators surface (frontend)

Depends on WI-2, WI-3.

- `apps/operator/app/(console)/operators`. Two-way root branch (`DF7-1`): `operator:create ∈ permissions` → issue `GET /platform/operators` + `GET /platform/roles`, render list + create form (email, display_name, role-select defaulting `provisioner`); not in permissions → render nothing and issue no gated call.
- 201 → invite-sent confirmation, invalidate `["platform-operators"]`. 409 → flag email. 422 → flag role-select.

**Done-check** (`operators.test.tsx`): `platform_admin` mounts list + form and a create round-trips into the list; `provisioner`-only operator issues **zero** calls to `GET /platform/operators` and `GET /platform/roles` (network assertion) and renders no form.

## WI-5 — Light up the "RBAC Management" nav entry (frontend)

Depends on WI-4.

- In `apps/operator/app/(console)/layout.tsx`, replace the visible-disabled "RBAC Management" placeholder with an `FE-13` `RequirePermission` gate on `operator:create`: **present** when held, **absent** otherwise (never visible-disabled; `DF7-2`).

**Done-check:** `platform_admin` sees the entry and it routes to `/operators`; `provisioner`-only operator does **not** see it (absent, not greyed); the other unbuilt placeholders (Catalogue Curation, Curation Inbox) remain visible-disabled.

## WI-6 — Genesis bootstrap end-to-end (verification; after WI-1)

Depends on WI-1, WI-2, WI-4, WI-5, V-ε.

- Exercise the full §1.1 sequence: seed present → `python -m app.cli.admin create-operator --email <dev> --display-name "<...>" --role platform_admin` with no `--actor` flags → accept invite, sign in → from the console create a second operator (a `provisioner`) via `POST /platform/operators`.

**Done-check:** the genesis `platform_admin` is login-capable (V-ε), reaches the operators surface, and successfully mints operator #2 from the UI; `create-operator` remains available as break-glass (not removed).

## WI-7 — Canonical update (volatile tier + decision-tier split)

Append-only; never renumber a live `INV-n`/`D-n`/`FE-n`/`DF-n`.

- **`API-ROUTES.md`**: add `POST /platform/operators`, `GET /platform/operators`, `GET /platform/roles` under §3, each gated `operator:create`. Annotate the gate column using the established plane-shorthand convention so it does not render `operator:operator:create` (V-β / NB5); while there, do not propagate the F7 `tenant:provision` vs `operator:tenant:provision` shorthand inconsistency.
- **`STATE.md`**: add the `UI-F8-OPERATOR-RBAC` section (operators surface, three new routes, the `platform_admin`/`operator:create` seed, the lit nav entry); record operator-creation as brought into `INV-49` compliance. **Do not** mark `INV-49`/`D-36` resolved or struck.
- **`DATA-MODEL.md`**: note the new seed rows (`platform_admin`, `operator:create`, grants) if the seed inventory is tracked there; no table/enum/DDL change.
- **`DECISIONS.md`**: append durable **`D-40`** and sprint-local **`DF8-1`, `DF8-2`, `DF8-3`** (keep the tiers distinct, NB4); record `DF8-3` deferrals (status toggle, role re-grant/revoke). Do not strike `INV-49`/`D-36`.
- **`INVARIANTS.md`**: no change (no new `INV-n`).
- **`FRONTEND.md`**: no change (`FE-13` reused; no new `FE-n`).
- **`PLATFORM-UX.md` §3**: fill the **Operator RBAC** line with the built intent (operators list + create, `operator:create` gate, status/role-mutation deferred); the sanctioned fill-as-you-go touch, mirroring the F7 §3 provisioning fill.

**Done-check:** `INDEX`/STATE ceilings reflect `D-40` and `DF8-3` as the latest ids; no live id renumbered; the new routes carry correct gate-column annotations; stable tier untouched beyond the `PLATFORM-UX` §3 fill.

---

## Appendix B — Source-verification register
Carried from `UI-F8-OPERATOR-RBAC_design.md` Appendix B (V-α, V-β, V-ε binding pre-flight; V-γ, V-δ). Clear in §0 above.