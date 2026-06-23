# DESIGN DOC (FINAL) · `UI-F8-OPERATOR-RBAC` — Operator Management Console

**Status:** FINAL, review folded · plane **PLATFORM (operator)** · type: surface an existing service over HTTP + UI + a platform-RBAC seed extension · durable route delta **+3** (`POST /platform/operators`, `GET /platform/operators`, `GET /platform/roles`) · schema/migration delta **0 DDL** (new `role`/`permission`/`role_permission` rows are seed content; whether they land via the data-seed loader or a migration revision branches on V-α) · new app: none · `FE-13` reused (no new convention) · sprint-local **DF8-1..3** · durable **D-40** · depends on `UI-F7-PROVISION` (`apps/operator` shell, `GET /platform/me`, `RequirePermission`/`FE-13`, the reserved "RBAC Management" nav slot), `provision_operator` (`app/services/operator_provisioning.py`, PRESENT) · brings operator creation into **`INV-49`** compliance · honours `PLATFORM-UX` §1–2, `INV-1`, `INV-8`, `INV-50`, `D-24`, the `D-23` "never self-service" principle (operator edition).

---

## Resolved decisions

| ID | Decision | Disposition |
|---|---|---|
| **DF8-1** | Management role name | `platform_admin` (avoids the tenant-side Membership `admin` collision, `ARCHITECTURE` §3 / PRD 4.9.1). NEW this sprint; only `provisioner` is seeded today. |
| **DF8-2** | Role composition | **Combined.** `platform_admin` holds **all** platform permissions via explicit `role_permission` grants (`D-40`). `provisioner` stays narrow (`tenant:provision`). New operators default to `provisioner` (CLI parity). |
| **DF8-3** | Sprint ceiling | Create plus list, mirroring `admin.py`. Operator **status toggle** and **role re-grant/revoke** deferred (no backing service; net-new, not a surfacing job). |
| **D-40** *(durable)* | `platform_admin` is superuser via explicit grants, never a wildcard | All-permissions is explicit `role_permission` rows, not a magic-role bypass. Any future platform permission must be granted to `platform_admin` in the same change. **Why:** a wildcard bypass conflates the authz layers and breaks DB-authoritative, role-resolved permission (`INV-8`, `D-24`). **Rejected:** superuser short-circuit in `require_permission`. |

---

## Review disposition

| Finding | Class | Disposition |
|---|---|---|
| premise (`provision_operator` PRESENT, genesis no-actor branch, schema present) | Blocking: none | Confirmed by reviewer against `admin.py` and DATA-MODEL §1; carried. |
| **NB1** · "three-way root branch" mischaracterized `DF7-1` | Non-blocking | **Accepted.** Retitled to **two-way** (§3.3); `DF7-1` is two-way and only two operator states exist (`DF8-2`). |
| **NB2** · "flips visible-disabled to live" loose vs `DF7-2` | Non-blocking | **Accepted.** §3.3 tightened: for a `provisioner`-only operator the RBAC Management entry is **absent** (`FE-13`), never greyed-and-enabled. |
| **NB3** · `OperatorProvisioningError → 502` diverges from `members.py` `→ 500` | Non-blocking | **Accepted, aligned to 500** (§3.2); no divergence carried, no `DF8-n` needed. |
| **NB4** · decision-tier split | Non-blocking | **Accepted.** `1/2/3 → DF8-1/2/3` (sprint-local), `D-40` durable; the canonical-update work item enforces the split. |
| **NB5** · gate-column shorthand collision (`operator:operator:create`) | Non-blocking | **Accepted, absorbed into V-β** and the canonical-update item. |
| **NB6** · seed → genesis ordering | Non-blocking | **Accepted.** Seed work item ordered ahead of any genesis done-check (handoff). |
| V-α / V-β / V-γ / V-δ / V-ε sharpening | Needs source verification | **Accepted.** Appendix B updated; V-γ binds the `source=` literal to the `POST /platform/provision` precedent; V-α admits the migration-borne seed path; V-β absorbs NB5 and the "no pre-existing `operator:*` / third role" check. |
| `D-40`, no new `INV-n`/`FE-n`, `D-4`/SoD non-inversion, `INV-49` framing, `INV-1`/`INV-50`, `D-23` operator edition, `DF7-1` carryover | Clean | Carried unchanged. |

---

## 1. Problem and frame

Operator creation is interactive-operational yet UI-less (CLI `create-operator` only), the same `INV-49`/`D-36` shape provisioning had before F7. The backend already exists: `provision_operator(email, display_name, role_key, actor, source)` does Cognito operator-pool user plus `operator` row plus initial role grant plus invite, the orphan-free `PAT-1` shape, the operator-plane twin of `provision_member`. So this sprint repeats the F7 move: surface an existing service over HTTP and UI, lighting up the "RBAC Management" slot F7 reserved as visible-disabled.

`INV-49` stays a live convention: this removes the operator-creation gap, it does not close the convention (F7 N1 discipline).

### 1.1 Genesis bootstrap (the load-bearing sequence)

Today only `provisioner` is seeded, so a genesis operator could provision tenants but not create operators in the UI, and operator #2 would still need the CLI. F8 seeds `platform_admin`, which closes the loop. The sequence, with its one hard ordering dependency:

1. **Seed runs first.** The platform-RBAC seed must already contain `operator:create`, the `platform_admin` role, and the grants. If absent, step 2 raises `RoleNotFound`. (Ordering: seed work item precedes the genesis done-check, NB6.)
2. **Genesis bootstrap, once, no actor.** `python -m app.cli.admin create-operator --email <you> --display-name "<...>" --role platform_admin`, no `--actor-sub/--actor-email`. This is the `_cli_actor → None` branch `admin.py` documents as genesis. It creates the operator-pool Cognito user, the `operator` row, the `platform_admin` grant, and the invite.
3. **Accept invite, sign in** via the operator-pool invite flow.
4. **All subsequent creation is UI.** As `platform_admin` the operator holds `operator:create` and mints every later operator (`platform_admin` or `provisioner`) through `POST /platform/operators`.

`create-operator` is **not removed** after bootstrap; it persists as break-glass (the operator-side mirror of F7 keeping `provision` as CLI fallback). Routine creation is the UI; CLI is bootstrap and break-glass only, exactly what `INV-49`/`D-36` reserve it for. The genesis path is only worth anything if the Cognito user is login-capable, not just a DB row: that is V-ε, binding.

## 2. PRESENT vs NEW

| Element | State | Note |
|---|---|---|
| `provision_operator`, `OperatorAlreadyExists`/`RoleNotFound`/`OperatorProvisioningError`, Cognito-pool user + invite, genesis no-actor branch | **PRESENT** | audit staging, `actor=None`, `source=` literal: V-γ |
| `provisioner` role + `tenant:provision` permission, seeded | **PRESENT** | seed home/mechanism: V-α |
| `apps/operator` shell, `GET /platform/me`, `RequirePermission`/`FE-13`, "RBAC Management" placeholder | **PRESENT** (F7) | placeholder goes live or absent per `FE-13` |
| `platform_admin` role; `operator:create` permission; `role_permission` grants (platform_admin → all; provisioner unchanged) | **NEW (seed)** | literals + free-key check: V-β |
| `POST /platform/operators`; `GET /platform/operators`; `GET /platform/roles` | **NEW (routes)** | |
| `OperatorCreate`/`OperatorCreated`/`OperatorListItem`/`RoleListItem` schemas | **NEW** | |
| `apps/operator/app/(console)/operators` surface | **NEW** | |

## 3. Design

### 3.1 Role and permission model
After this sprint, two seeded roles: `provisioner` (PRESENT, `tenant:provision`) and `platform_admin` (NEW, every permission via explicit `role_permission` rows, `D-40`). One new permission, byte-exact `operator:create` (the `noun:verb` convention `tenant:provision` follows; the `operator:` in API-ROUTES gate columns is plane shorthand, not part of the key, V-β). New operators default to `provisioner`; a `platform_admin` may mint either role. Authority stays permission-through-role, DB-resolved, never from claims (`INV-8`, `D-24`).

### 3.2 Backend routes
All three gate on `operator:create`, the `DF7-1` shared-gate carryover: there is no list-but-not-create operator, so the list and the role read ride the same permission as create (no second gate left exposed). This rests on V-β confirming no pre-existing `operator:*` permission or third operator-management role.

- `POST /platform/operators` → wraps `provision_operator(..., actor=<calling operator>, source=<match POST /platform/provision>)`. Errors: `OperatorAlreadyExists` → 409, `RoleNotFound` → 422, `OperatorProvisioningError` → **500** (aligns to `members.py::create_member`, NB3). Response `{operator_id, cognito_sub}`.
- `GET /platform/operators` → list operators with roles and `OperatorStatus` (net-new; `admin.py` has no `list-operators`).
- `GET /platform/roles` → assignable roles for the form select.

Each create stages a `PlatformAuditEvent` for the HTTP actor (`PLATFORM-UX` §2); the console adds no audit of its own. Whether `provision_operator` already stages it on the HTTP `source` is V-γ.

### 3.3 Frontend surface
The "RBAC Management" nav entry resolves through `FE-13` (`RequirePermission`) on `operator:create`: **present** for an operator holding it, **absent** for a `provisioner`-only operator (never visible-disabled; visible-disabled is reserved for *unbuilt* surfaces per `DF7-2`, and this one is now built). Surface at `apps/operator/app/(console)/operators`, mirroring the F7 provisioning surface and its **two-way** root branch (`DF7-1`):

- **`operator:create ∈ permissions`:** issue `GET /platform/operators` and `GET /platform/roles`; render the operator list plus a create-operator form (email, display_name, role-select defaulting to `provisioner`).
- **`operator:create ∉ permissions`:** the nav entry is absent and **no gated call is issued** (the `provisioner`-only operator never touches these routes).
- 201 → invite-sent confirmation, invalidate and refetch `["platform-operators"]`. 409 → flag the email field. 422 → flag the role-select.

Operator-plane register per `PLATFORM-UX` §2: density, operational vocabulary, no adoption layering. Desktop-only (`FE-1`).

### 3.4 Seed extension
Add the `platform_admin` role, the `operator:create` permission, and `role_permission` grants (`platform_admin` → all permissions including `tenant:provision` and `operator:create`; `provisioner` unchanged), via **the mechanism the existing platform-RBAC seed uses** (V-α: this may be a migration that created `platform_rbac`, not the `data/seed/` + `scripts/seed/` loader, which `INV-48` scopes to GLOBAL reference data only; do not assume the loader path). Operators are not seed data; the genesis `platform_admin` comes from the §1.1 bootstrap.

## 4. Conventions and invariants

1. **`INV-49`** (CONVENTION) — operator-creation gap removed; convention stays live.
2. **`INV-50`**, **`INV-1`** — upheld: operator BFF, operator origin/pool only.
3. **`INV-8`**, **`D-24`** — upheld: permission-through-role, DB-resolved; `D-40` keeps `platform_admin` explicit, not a bypass.
4. **`FE-13`** — reused; no new convention. `DF7-2` already governs the nav transition.
5. **`D-23` principle (operator edition)** — operator creation is never self-service; only `provision_operator` via CLI (bootstrap/break-glass) or `POST /platform/operators` (console), never a public surface.

No new `INV-n`, no new `FE-n`. Schema/migration delta 0 DDL (pending V-α: migration-borne seed rows are still not DDL).

## 5. Out of scope (named)
Operator status enable/disable; role re-grant/revoke; multi-role assignment at create (the service takes one `role_key`); operator self-management; catalogue curation; the curation-task inbox. The first two are the obvious F9 follow-on once their services exist.

---

## Appendix A — Open decisions (resolved)
None remaining; `DF8-1..3` and `D-40` resolved above. The wildcard-superuser alternative is recorded as rejected under `D-40`.

## Appendix B — Source-verification register (verify live before execution; `D-21`)

| ID | Item | Where | Binds | Pre-flight |
|---|---|---|---|---|
| **V-α** | Platform `role`/`permission`/`role_permission` seed home and mechanism (data-seed loader vs the migration that created `platform_rbac`); confirm only `provisioner`/`tenant:provision` exist today. The work-item form (seed file vs migration revision) branches on this; "0 DDL" survives either way. | `scripts/seed/`, `data/seed/`, `alembic/` platform-rbac revision | the seed work item form | **BINDING** |
| **V-β** | Byte-exact new permission literal (`operator:create` proposed); confirm `platform_admin` is a free role key; confirm **no pre-existing `operator:*` permission or third operator-management role** (the §3.2 shared-gate assertion rests on this); handle the API-ROUTES gate-column shorthand so it does not render `operator:operator:create` (NB5). | `permission`/`role` seed, `app/auth/operator_authz.py`, `API-ROUTES` | the route gate + `FE-13` byte-exact match + shared-gate | **BINDING** |
| **V-γ** | `provision_operator` exact signature/return/exceptions (confirm from `admin.py`); whether it stages a `PlatformAuditEvent` on the HTTP source; `actor=None` handling; **bind the `source=` literal to whatever `POST /platform/provision` passes** (`tenants.py` shows `"http"`), do not invent a third value. | `app/services/operator_provisioning.py`, `app/routers/platform/tenants.py` | route wrapping, attribution (§3.2) | |
| **V-δ** | `Operator` (`status = OperatorStatus`, labels), `operator_role`, `role` fields for the list; confirm no `GET /platform/operators` exists yet (net-new). | `app/models/platform_rbac.py`, `app/routers/platform/` | the list route + columns | |
| **V-ε** | `provision_operator` creates a login-capable operator-pool Cognito user + invite (the CLI asserts an invite email); operator-pool app-client/invite flow wired. | `app/services/operator_provisioning.py`, `cognito_helpers.py`, `infra/` | a genesis `platform_admin` can actually sign in (F7 V-8 analogue) | **BINDING** |