# UI-F9-MEMBERS — Final Design Doc (post-review)

**Status:** final, review folded. Supersedes v3. **0 backend delta, 0 new routes/tables/enums/migrations, 0 stable-tier amendments.** Single plane (tenant). Specimen rendered and binding (§7).
**Sprint thesis:** Ship the tenant-plane member-management surface so an admin invites members and staffs governance roles, with SoD made visible before the act, making the multi-member review-to-authorise loop demonstrable.
**OPEN-4:** deferred by decision (DF-F9-1). No self-assignment or SoD relaxation.
**Review disposition:** B1 (backend-delta premise dead, `MeRead` already carries `role`+`tenant_name`) accepted; B2 (roles-held source) resolved; B3 (FE-16 orthogonality) resolved; B4 (self-case vs absence model) resolved without an FE-8 carve-out; B5 (DF-F9-3 defined); NB1/NB2/NB3 folded; SV1-SV5 in §0/Appendix B.
**Canon ceilings cited:** INV-70, D-52, FE-23 (per INDEX). **Binding: confirm live ceilings before minting (SV1); new IDs land above the live ceiling, not INDEX's.**
**Cross-refs grounded:** INV-7, INV-2, INV-56, INV-69, INV-70, D-4, D-5, D-22, D-48, D-52, DF2-5, DF5-7, DF7-1, FE-8, FE-13, FE-16, FE-20..23, DOMAIN §7, OPEN-4.

---

## §0 Pre-flight verify checklist (D-21 — live reads before encoding)

| # | Verify | Why it matters | Source |
|---|---|---|---|
| V0 | **Live canon ceilings** for INV-n / D-n / FE-n / DF-n (D-21 canary; INDEX lags STATE per SV1). | New IDs (D-53, INV-71, FE-24, DF-F9-1/3) must mint above the **live** ceiling. If live exceeds INDEX's, renumber contiguously. | `STATE`, `DECISIONS`, `INVARIANTS`, `FRONTEND` (live) |
| V3 | `assert_governance_assignable` exact reject conditions: `acting == subject` self-block **and** the matrix conflict check. **Read-only; not modified this sprint.** | Every UI disabled-with-reason must mirror a real 403 path (INV-71); the self-block must mirror as control-absence. **Stop-and-escalate on divergence.** | `app/services/governance.py` (live) |
| V4 | Live `governance_role` keys (`system_owner / contributor / reviewer / authoriser / auditor`) + `governance_role_conflict` rows (9 conflicting pairs; only `system_owner+contributor` composable). | The SoD-visible control binds these verbatim. | `pg` read (live) |
| V5 | Contract shapes at HEAD: `MemberCreate{email,name}`, `MemberCreated`, `MemberRead{user_id,membership_id,email,name,role,status,created_at}`, `MemberListResponse` (keyset), `GovernanceRoleAssignmentCreate`, `GovernanceRoleAssignmentRead`, `GovernanceCatalogueRead`. | UI binds verbatim; no re-grep. `MemberRead` carries **no** governance roles (drives B2). | `packages/api-client/src/contracts/*`, `app/schemas/{member,governance}.py` (live) |
| V6 | **`MeRead.role` literal casing** the client must compare (`"admin"`/`"member"` vs `ADMIN`/`MEMBER`); `me.py` returns `ctx.role`, the list emits `membership.role.value`. | Nav gating + page root-branch compare against the literal; a casing mismatch silently breaks both. | `app/routers/me.py`, `members.py` (live) |
| V7 | Existence of a **tenant-wide** `GET /governance-roles/assignments` (no membership filter). | Decides B2: list-column roles-held is viable **only** if this exists (single grouped fetch, 0 delta). If absent, roles-held is panel-only; **do not add the route** (would be backend delta). | `app/routers/governance_roles.py`, `API-ROUTES` (live) |
| V8 | Smoke: `provision_member` returns `membership_id` at invite; `_cognito_status_to_accept` (`CONFIRMED→accepted`, else `pending`); membership row exists pre-accept. | Pending member is assignable (confirmed by review SV5; smoke only). | `app/services/cognito_helpers.py`, `member_provisioning.py` (live) |
| V9 | No tenant-plane route already lists a member's display identity beyond `GET /members`. | Single-home-per-truth: no second identity home. | `API-ROUTES` + routers (live) |

`MeRead` admin-axis read (former v3 V6) is **resolved PRESENT** per review B1; no longer verified.

---

## 1. Objective

Ship member management on the tenant plane so an admin invites members and staffs governance roles, with the SoD conflict surfaced before the act. Unblocks the multi-member review-to-authorise loop (D-4), undemonstrable with one person.

**OPEN-4 deferred (DF-F9-1).** Stay compliant with the self-assignment block (D-5) and SoD model (INV-7) until a compelling, justifiable reason to relax exists. Consequence accepted and documented: a no-governance-role admin can invite and grant roles to **others**, but cannot obtain a governance role themselves through the UI (self-assignment blocked by D-5; invited members are always `MEMBER`, no second-admin path). The dev workaround (direct `governance_role_assignment` insert; multi-role self-setup for testing) remains the only owner-self path. Not a silent gap.

**Demo arc unlocked (multi-member):** an admin with a governance role (dev: self-granted via workaround; prod: a pure-admin staffing others) → Members → invites a reviewer and an authoriser → assigns roles, SoD control blocks any second role on a single membership except `system_owner+contributor` → invitees accept via Cognito → full review-to-authorise loop demonstrable across distinct parties.

---

## 2. Scope

**In (all 0 backend delta):**
1. **Members surface (tenant plane, NEW, born-compliant C0):** member list (name / email / admin-role / accept-status), invite member, per-member governance-role assign/revoke with SoD-conflict-visible control. **Roles-held** renders in the per-member panel via `GET /governance-roles/assignments/member/{id}` (guaranteed); a list **column** is added only if V7 confirms a tenant-wide assignments route (single grouped fetch, names joined from catalogue), else panel-only. Admin-axis gated; absent for non-admins.
2. **Members nav entry** + **page root-branch guard** (DF-F9-3, NB1): both gated on `MeRead.role == admin`; non-admin direct-nav suppresses the gated `GET /v1/members` call (no 403-masked empty state).
3. **Accept-status chip:** neutral non-semantic chrome (B3); pending/accepted distinguished by fill/weight, **no `--verdict-*`**.

**Out:** OPEN-4 resolution / self-assignment relaxation (DF-F9-1); member deactivation / resend-invite (STATE deferred); per-object `scope_id` assignment (D-22 reserved seam); `Membership.role` edit (no route); F1 / F2-systems / F3-F8 composition passes (separate track).

---

## 3. Resolved decisions

| ID | Decision | Annot. | Rationale | Rejected |
|---|---|---|---|---|
| **DF-F9-1** | OPEN-4 remains open; deferred this sprint. No self-assignment or SoD relaxation. | NEW (sprint-local) | Stay compliant with D-5/INV-7 until a justifiable reason to relax exists; dev unblocks via workaround. | Resolving OPEN-4 now (provision seed / runtime grace / self-assign relaxation). |
| ~~DF-F9-2~~ | **Struck** (was: additive `MeRead` admin flag). | — | Review B1: `MeRead` already carries `role`. No backend delta. Number retired. | — |
| **DF-F9-3** | **Tenant-plane administrative-axis nav + page gating:** the Members nav entry renders and the page issues its gated calls iff `MeRead.role == admin`; otherwise the entry is absent and no `GET /v1/members` is issued. New ground, distinct from FE-8 (act-SoD) and FE-13 (operator-permission). | NEW (sprint-local) | Tenant-plane ADMIN/MEMBER gating is uncovered by existing conventions; absence (not disabled) matches the established no-gated-call pattern (DF7-1/DF2-5/DF5-7). | Render-then-403 (shows a non-functional entry; masks empty state). |
| **D-53** | Members UI scope = **full**: list + invite + assign/revoke with SoD-visible control. | NEW | Half-scope leaves the SoD loop undemonstrable. | CRUD-only, role assignment deferred. |

**PRESENT verified facts (no ID minted, per NB2/NB3):**
- Route reuse: `POST/GET /v1/members`, `GET /governance-roles/catalogue`, `GET /governance-roles/assignments/member/{id}`, `POST/DELETE /governance-roles/assignments` exist at HEAD with the claimed gates and shapes (review Clean).
- Pending-member assignability: the `membership` row exists at invite; assignment targets `membership_id`; no accept-status gate in the assign path (review Clean / SV5).

---

## 4. Surface design (tenant plane)

### 4.1 Nav + page gating (DF-F9-3, NB1)
New sidebar entry **Members**, below `Audit` (administration, DOMAIN §7 admin axis), rendered iff `MeRead.role == admin` (V6 casing). Absent for non-admins, never greyed. The page root-branches on the same predicate: a non-admin who direct-navigates gets the established not-authorised treatment and issues **no** gated call (pattern: DF7-1 / DF2-5 / DF5-7).

### 4.2 Members list region
- `GET /v1/members` (keyset; INV-2 `membership`→`app_user` join; Cognito accept status).
- Columns: name, email, administrative role, **accept-status chip (neutral chrome, B3)**, row action → role panel. Roles-held column conditional on V7 (else panel-only).
- INV-70 states: owner-only first-run (prompt to invite), loading (`Skeleton`, FE-22), error (`ErrorState`, FE-22). "Empty" is effectively owner-only since the owner row always renders.
- Status chip: **non-semantic chrome** (WhoseCourtIndicator analogue); `accepted` = muted fill, `pending` = outline. No `--verdict-*`, no new channel. FE-16 untouched.

### 4.3 Invite member
- `POST /v1/members` (`MemberCreate{email,name}`) → `MemberCreated` (pending). FE-23 kit. Invalidate `["members"]` on success.
- Operational note (not a blocker): Cognito invite delivery + accept is out-of-band; surface stays pending until Cognito reports accepted.

### 4.4 Governance-role assignment (SoD-visible) — specimen-bound (§7)
- Catalogue `GET /governance-roles/catalogue` (5 roles + matrix); member grants `GET /governance-roles/assignments/member/{membership_id}`; assign `POST /governance-roles/assignments`; revoke `DELETE /governance-roles/assignments/{assignment_id}`.
- **Conflict case (other members) — INV-71:** each catalogue role is listed; a role conflicting with a held grant (per matrix) is **disabled-with-reason** naming the conflict ("Conflicts with system owner: separation of duties"). This is FE-8's **transient** branch (the bar is resolvable by revoking the held role). The single composable pair (`system_owner+contributor`) shows the second role assignable. Client computes affordance from the matrix only; **server `assert_governance_assignable` (INV-7) is the authority** and a forged call 403s.
- **Self case (acting admin's own membership) — B4/A-6:** the assignment control is **absent** (structural D-5 bar, honoured per FE-8/INV-56), replaced by an FE-22-style explanatory **note** (copy, not a disabled control, so INV-56 is not tripped): "Governance roles are assigned by another administrator, to preserve separation of duties." No FE-8 carve-out; stable tier untouched.

---

## 5. Backend delta

**None.** No route, table, enum, migration, schema field, or stable-tier change. `assert_governance_assignable` is read-only (V3, verify-not-modify). `MeRead` already carries `role` + `tenant_name` (B1).

---

## 6. Proposed invariants / FE conventions (mint above live ceiling, V0)

| ID | Tag | Statement | Refs |
|---|---|---|---|
| **INV-71** | CONVENTION | In the governance-role assignment UI, a **resolvable** SoD conflict (member holds a conflicting role) is shown disabled-with-reason naming the conflict before the act (FE-8 transient branch). The **structural** self-assignment bar (D-5) is honoured by control **absence** (FE-8/INV-56), optionally accompanied by an explanatory note (copy, not a control). The client never substitutes for the server; `assert_governance_assignable` (INV-7) is the authority and a forged call 403s. | INV-7, INV-56, D-4, D-5, FE-8, FE-24 |
| **FE-24** | — | Members surface: administrative-axis nav + page gating (DF-F9-3); member list from `GET /v1/members` (INV-2); accept-status as **neutral non-semantic chrome**, not the verdict channel (FE-16 untouched); SoD-visible assign control (INV-71); pending member assignable; composed from FE-20..23 kit (INV-69) with all four INV-70 states. | FE-8, FE-13, FE-16, FE-20..23, INV-2, INV-56, INV-69, INV-70, INV-71, DF-F9-3 |

Born-compliant: the Members surface is bound by INV-69/INV-70 natively (debt register: "Member management is born compliant").

**Stable tier: UNTOUCHED.** D-5, INV-7, INV-28, INV-56, FE-8, FE-16, DOMAIN §7, WKF-6 all unchanged.

---

## 7. Rendered specimen (binding — show-don't-tell)

The specimen rendered in chat (`members_sod_role_assignment_spec`) is the binding visual spec for §4.2/§4.4. It fixes: the neutral accept-status chips (B3); the assignment panel with a held role, the composable `contributor` assignable, and `reviewer`/`authoriser`/`auditor` disabled-with-reason (INV-71 conflict branch); and the self panel with the assignment control **absent** plus the FE-22 note (B4/A-6). Binding copy uses a colon, not an em dash: "Conflicts with system owner: separation of duties". The agent builds to this with live tokens (INV-68: does not originate layout/composition). List and invite regions are straight FE-23 kit composition.

---

## Appendix A — Open decisions

- **A-1** RESOLVED → DF-F9-1 (OPEN-4 deferred).
- **A-3** RESOLVED → D-53 (full UI scope).
- **A-4** Nav label/placement: **Members**, below Audit. Confirm (only remaining cosmetic open).
- **A-6** RESOLVED → self case = control absent + FE-22 note (B4); specimen-bound.
- ~~A-5~~ Struck (B1; `MeRead` already carries `role`).

## Appendix B — Source-verification register (D-21)

- **B-1 (V3) [stop-and-escalate]:** `assert_governance_assignable` reject conditions, read-only; UI disabled-with-reason and self-absence must mirror server behaviour exactly.
- **B-2 (V7):** tenant-wide `GET /governance-roles/assignments` existence → decides list-column vs panel-only roles-held. **No route added if absent.**
- **B-3 (V4):** live `governance_role` keys + 9 conflict rows (bind the SoD control).
- **B-4 (V5/V6):** contract shapes + `MeRead.role` literal casing (nav/page compare).
- **B-5 (V9):** no pre-existing second identity home.
- **B-6 (V0):** live canon ceilings before minting (SV1).
- **B-7 (V8):** pending-member assignability smoke (review-confirmed).

---

*Handoff is the companion artifact `UI-F9-MEMBERS-handoff.md` (execution-only).*