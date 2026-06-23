"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface PlatformMe {
  id: string;
  email: string | null;
  display_name: string | null;
  permissions: string[];
}

interface OperatorListItem {
  id: string;
  email: string;
  display_name: string | null;
  status: string;
  roles: string[];
}

interface OperatorCreated {
  operator_id: string;
  cognito_sub: string;
}

interface OperatorCreate {
  email: string;
  display_name: string;
  role_key: string;
}

interface RoleListItem {
  key: string;
  description: string | null;
}

const PERM_OPERATOR_CREATE = "operator:create";

const EMPTY_FORM: OperatorCreate = {
  email: "",
  display_name: "",
  role_key: "provisioner",
};

type FieldError = Partial<Record<keyof OperatorCreate, string>>;

function validateForm(form: OperatorCreate): FieldError {
  const errors: FieldError = {};
  if (!form.email.trim()) errors.email = "Required";
  else if (form.email.length > 320) errors.email = "Max 320 characters";
  else if (!form.email.includes("@")) errors.email = "Invalid email";

  if (!form.display_name.trim()) errors.display_name = "Required";
  else if (form.display_name.length > 255) errors.display_name = "Max 255 characters";

  if (!form.role_key.trim()) errors.role_key = "Required";

  return errors;
}

function OperatorList({ operators }: { operators: OperatorListItem[] }) {
  if (operators.length === 0) {
    return <p>No operators yet.</p>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>Email</th>
          <th>Display name</th>
          <th>Status</th>
          <th>Roles</th>
          <th>ID</th>
        </tr>
      </thead>
      <tbody>
        {operators.map((op) => (
          <tr key={op.id}>
            <td>{op.email}</td>
            <td>{op.display_name ?? "—"}</td>
            <td>{op.status}</td>
            <td>{op.roles.join(", ")}</td>
            <td>{op.id}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CreateOperatorForm({
  roles,
  onPermissionLost,
}: {
  roles: RoleListItem[];
  onPermissionLost: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState<OperatorCreate>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<FieldError>({});
  const [lastResult, setLastResult] = useState<OperatorCreated | null>(null);

  const mutation = useMutation({
    mutationFn: (body: OperatorCreate) =>
      api.post<OperatorCreated>("/platform/operators", body),
    onSuccess: (result) => {
      setLastResult(result);
      setForm(EMPTY_FORM);
      setFieldErrors({});
      qc.invalidateQueries({ queryKey: ["platform-operators"] });
    },
    onError: async (err: unknown) => {
      const response = err as { status?: number; body?: unknown };
      if (response.status === 409) {
        setFieldErrors((prev) => ({ ...prev, email: "Already exists" }));
      } else if (response.status === 422) {
        setFieldErrors((prev) => ({ ...prev, role_key: "Invalid role" }));
      } else if (response.status === 403) {
        qc.invalidateQueries({ queryKey: ["platform-me"] });
        onPermissionLost();
      }
    },
  });

  function handleChange(field: keyof OperatorCreate, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setFieldErrors((prev) => ({ ...prev, [field]: undefined }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errors = validateForm(form);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setFieldErrors({});
    mutation.mutate(form);
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Create new operator">
      <div>
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          value={form.email}
          onChange={(e) => handleChange("email", e.target.value)}
          aria-describedby={fieldErrors.email ? "email-error" : undefined}
        />
        {fieldErrors.email && (
          <span id="email-error" role="alert">
            {fieldErrors.email}
          </span>
        )}
      </div>

      <div>
        <label htmlFor="display_name">Display name</label>
        <input
          id="display_name"
          value={form.display_name}
          onChange={(e) => handleChange("display_name", e.target.value)}
          aria-describedby={fieldErrors.display_name ? "display_name-error" : undefined}
        />
        {fieldErrors.display_name && (
          <span id="display_name-error" role="alert">
            {fieldErrors.display_name}
          </span>
        )}
      </div>

      <div>
        <label htmlFor="role_key">Role</label>
        <select
          id="role_key"
          value={form.role_key}
          onChange={(e) => handleChange("role_key", e.target.value)}
          aria-describedby={fieldErrors.role_key ? "role_key-error" : undefined}
        >
          {roles.map((r) => (
            <option key={r.key} value={r.key}>
              {r.key}
            </option>
          ))}
        </select>
        {fieldErrors.role_key && (
          <span id="role_key-error" role="alert">
            {fieldErrors.role_key}
          </span>
        )}
      </div>

      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Creating…" : "Create operator"}
      </button>

      {lastResult && (
        <p role="status">Invite sent — operator {lastResult.operator_id}</p>
      )}
    </form>
  );
}

export default function OperatorsPage() {
  const qc = useQueryClient();

  const { data: me, isLoading: meLoading } = useQuery({
    queryKey: ["platform-me"],
    queryFn: () => api.get<PlatformMe>("/platform/me"),
  });

  const permissions = me?.permissions ?? [];
  const hasCreate = permissions.includes(PERM_OPERATOR_CREATE);

  const { data: operators = [] } = useQuery({
    queryKey: ["platform-operators"],
    queryFn: () => api.get<OperatorListItem[]>("/platform/operators"),
    enabled: hasCreate,
  });

  const { data: roles = [] } = useQuery({
    queryKey: ["platform-roles"],
    queryFn: () => api.get<RoleListItem[]>("/platform/roles"),
    enabled: hasCreate,
  });

  if (meLoading) return <p>Loading…</p>;

  if (!hasCreate) {
    return null;
  }

  return (
    <section aria-label="Operators">
      <h1>Operators</h1>

      <section aria-label="Operator list">
        <h2>Operators</h2>
        <OperatorList operators={operators} />
      </section>

      <section aria-label="Create new operator">
        <h2>Create an operator</h2>
        <CreateOperatorForm
          roles={roles}
          onPermissionLost={() => qc.invalidateQueries({ queryKey: ["platform-me"] })}
        />
      </section>
    </section>
  );
}
