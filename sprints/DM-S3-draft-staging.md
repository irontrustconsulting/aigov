# DM-S3 — Draft Staging & Resume (core) — Execution Handoff

**Execution-only.** Rationale and review history live in `DM-S3-draft-staging-design.md`. Do not originate design (INV-68): stop and flag if a work item needs an unspecified choice. Build defects exempt. **The dashboard indicator and the nudge decision are NOT in this sprint — they are DM-S3b.**

**Mint floors:** D ≥ 65, INV ≥ 78, FE ≥ 27. New ids: D-66, INV-79, FE-28, DF-D3-1..6. Never renumber a live id. **0 classifier change.** STATE "Current through: DM-S2" is the floor (INDEX lags at UI-V2 — refresh it in WI-6).

---

## §0 — Pre-flight (binding; grep-first across ALL core layers; halt on divergence)

- **P-0:** HEAD; floors D ≥ 65 / INV ≥ 78 / FE ≥ 27.
- **P-1:** confirm every core layer is covered — FastAPI router/service/model/migration (`app/`), `@irontrust/api-client` draft contracts (`packages/`), `lib/intake` hooks (`apps/tenant/`), wizard reducer/steps (`systems/new`). (Dashboard is DM-S3b.)
- **P-2:** confirm `WizardState` holds the pre-boundary fields + `step` (cursor).
- **P-4:** confirm the INV-77 RLS pattern (`tenant_id` FK NOT NULL + policy `tenant_id = current_setting('app.current_tenant', true)::uuid`) and the `gov:system_owner` gate.
- **SV-3:** confirm adding optional `draft_id` to `RegistrationCreate` + an in-handler delete after the flushes leaves `TestRegistrationAtomicity` green.

---

## Work items (dependency-ordered)

### WI-1 — Backend: table + endpoints + discard
- **Migration:** `draft_registration` (`id`; `tenant_id` FK `tenant` `ondelete=CASCADE`, RLS policy as INV-77; `owner_user_id` FK `app_user` `ondelete=CASCADE`; `draft_blob` JSONB; `created_at`; `updated_at`). **`UniqueConstraint(tenant_id, owner_user_id)`** (plain, not partial).
- **Router + service** (`draft_registrations.py`, `gov:system_owner`): `POST` get-or-create (SELECT the caller's active draft first, else insert); `PATCH /{id}` merge/replace `draft_blob` (last-write-wins, no `lock_version`); `GET /active` → draft or `204`; `DELETE /{id}` discard. **Every read/write adds `WHERE owner_user_id = ctx.user_id`** — RLS scopes tenant only, not user.
- **`POST /registrations`:** add optional `draft_id`; when present, `DELETE` the draft inside the same transaction (after the system/use_case flushes, before request-end commit).
- **Done:** CRUD works owner-scoped; a second user in the same tenant cannot touch the first user's draft (owner-filter test, distinct from RLS); cross-tenant read returns nothing (RLS); `pg_policies` shows the policy; `UniqueConstraint` present; `POST /registrations` with `draft_id` deletes the draft on success and leaves it on rollback; `TestRegistrationAtomicity` green.

### WI-2 — `packages/api-client`
- Add `DraftRegistrationRead` + the four draft methods; add optional `draft_id` to `RegistrationCreate`.
- **Done:** package builds; contracts typecheck.

### WI-3 — `apps/tenant/lib/intake`
- `useDraft` hooks: `useGetOrCreateDraft`, `usePatchDraft`, `useActiveDraft`, `useDiscardDraft`. Thread `draft_id` into `useRegister`.
- **Done:** hooks compile; `useActiveDraft` returns the caller's draft or null.

### WI-4 — `packages/ui`: `ResumePrompt` (FE-28)
- Resume-or-start-over panel: product name, progress, last-edited; primary **Resume**, secondary **Start over**. No new tokens; reuse the kit.
- **Done:** renders both actions; axe clean; FE-28 registered.

### WI-5 — Wizard: persist-on-transition + resume
- **Persist:** first pre-boundary advance get-or-creates the draft; each subsequent pre-boundary advance `PATCH`es `draft_blob` with the **clamped** `step` (one of `drill-down`/`intake`/`prefill`/`use-case`). **No `PATCH` on or after `REGISTERED`.**
- **Resume entry:** on entering `/systems/new`, call `useActiveDraft`; if present, render `ResumePrompt`. Resume loads `draft_blob` into wizard state and lands on the clamped saved `step`; Start over discards and resets to `drill-down`.
- **Boundary:** the use-case step's `POST /registrations` passes `draft_id`.
- **Done:** advancing writes the draft; re-entering shows `ResumePrompt`; Resume restores and lands no later than `use-case` (clamp asserted); Start over discards; a full run promotes and the draft is gone.

### WI-6 — Canon update (mandatory; last)
- **STATE:** registration wizard draft-staged and resumable via the front door; `draft_registration` (tenant RLS, one active per user via plain unique, owner-filtered access, CASCADE FKs); four draft endpoints + atomic `draft_id` discard on `POST /registrations`; `ResumePrompt`. Note DM-S3b owes the dashboard indicator + nudge decision.
- **API-ROUTES:** add the four draft routes + `draft_id` on `POST /registrations`.
- **DATA-MODEL:** add `draft_registration`.
- **FRONTEND:** FE-28.
- **INDEX.md:** refresh "Current scope" (it lags at UI-V2; bring it to DM-S3) and the ceiling line.
- **Append:** D-66, INV-79, FE-28, DF-D3-1..6. Never renumber; stable tier untouched.
- **Done:** canonicals updated incl. INDEX; ids appended above floors; STATE "Current through" advanced to DM-S3.

---

**Full suite green before done.** New tests cover WI-1 (owner-scoping, RLS, get-or-create, atomic discard), WI-5 (persist, resume, step clamp). No dashboard test changes in this sprint.