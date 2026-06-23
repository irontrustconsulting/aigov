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

interface TenantListItem {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

interface ProvisionResponse {
  tenant_id: string;
  owner_id: string;
}

interface ProvisionRequest {
  org_name: string;
  slug: string;
  owner_email: string;
  owner_name: string;
}

const PERM_PROVISION = "tenant:provision";

const EMPTY_FORM: ProvisionRequest = {
  org_name: "",
  slug: "",
  owner_email: "",
  owner_name: "",
};

type FieldError = Partial<Record<keyof ProvisionRequest, string>>;

function validateForm(form: ProvisionRequest): FieldError {
  const errors: FieldError = {};
  if (!form.org_name.trim()) errors.org_name = "Required";
  else if (form.org_name.length > 255) errors.org_name = "Max 255 characters";

  if (!form.slug.trim()) errors.slug = "Required";
  else if (form.slug.length > 100) errors.slug = "Max 100 characters";
  else if (!/^[a-z0-9-]+$/.test(form.slug))
    errors.slug = "Lowercase letters, digits, and hyphens only";

  if (!form.owner_email.trim()) errors.owner_email = "Required";
  else if (form.owner_email.length > 320) errors.owner_email = "Max 320 characters";
  else if (!form.owner_email.includes("@")) errors.owner_email = "Invalid email";

  if (!form.owner_name.trim()) errors.owner_name = "Required";
  else if (form.owner_name.length > 255) errors.owner_name = "Max 255 characters";

  return errors;
}

function TenantList({ tenants }: { tenants: TenantListItem[] }) {
  if (tenants.length === 0) {
    return <p>No tenants provisioned yet.</p>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Slug</th>
          <th>Provisioned</th>
          <th>ID</th>
        </tr>
      </thead>
      <tbody>
        {tenants.map((t) => (
          <tr key={t.id}>
            <td>{t.name}</td>
            <td>{t.slug}</td>
            <td>{new Date(t.created_at).toLocaleString()}</td>
            <td>{t.id}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ProvisionForm({
  onSuccess,
  onPermissionLost,
}: {
  onSuccess: (result: ProvisionResponse) => void;
  onPermissionLost: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState<ProvisionRequest>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<FieldError>({});
  const [conflict, setConflict] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<ProvisionResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (body: ProvisionRequest) =>
      api.post<ProvisionResponse>("/platform/provision", body),
    onSuccess: (result) => {
      setLastResult(result);
      setForm(EMPTY_FORM);
      setFieldErrors({});
      setConflict(null);
      qc.invalidateQueries({ queryKey: ["platform-tenants"] });
      onSuccess(result);
    },
    onError: async (err: unknown) => {
      const response = err as { status?: number; body?: unknown };
      if (response.status === 409) {
        const detail: string =
          (response.body as { detail?: string } | null)?.detail ?? "";
        if (detail.includes("slug")) {
          setFieldErrors((prev) => ({ ...prev, slug: "Already provisioned" }));
        } else if (detail.includes("user already exists")) {
          setFieldErrors((prev) => ({
            ...prev,
            owner_email: "A user with this email already exists",
          }));
        } else {
          setConflict(detail || "Already provisioned");
        }
      } else if (response.status === 403) {
        qc.invalidateQueries({ queryKey: ["platform-me"] });
        onPermissionLost();
      }
    },
  });

  function handleChange(field: keyof ProvisionRequest, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    setFieldErrors((prev) => ({ ...prev, [field]: undefined }));
    setConflict(null);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errors = validateForm(form);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setFieldErrors({});
    setConflict(null);
    mutation.mutate(form);
  }

  return (
    <form onSubmit={handleSubmit} aria-label="Provision new tenant">
      <div>
        <label htmlFor="org_name">Organisation name</label>
        <input
          id="org_name"
          value={form.org_name}
          onChange={(e) => handleChange("org_name", e.target.value)}
          aria-describedby={fieldErrors.org_name ? "org_name-error" : undefined}
        />
        {fieldErrors.org_name && (
          <span id="org_name-error" role="alert">
            {fieldErrors.org_name}
          </span>
        )}
      </div>

      <div>
        <label htmlFor="slug">Slug</label>
        <input
          id="slug"
          value={form.slug}
          onChange={(e) => handleChange("slug", e.target.value)}
          aria-describedby={fieldErrors.slug ? "slug-error" : undefined}
        />
        {fieldErrors.slug && (
          <span id="slug-error" role="alert">
            {fieldErrors.slug}
          </span>
        )}
      </div>

      <div>
        <label htmlFor="owner_email">Owner email</label>
        <input
          id="owner_email"
          type="email"
          value={form.owner_email}
          onChange={(e) => handleChange("owner_email", e.target.value)}
          aria-describedby={fieldErrors.owner_email ? "owner_email-error" : undefined}
        />
        {fieldErrors.owner_email && (
          <span id="owner_email-error" role="alert">
            {fieldErrors.owner_email}
          </span>
        )}
      </div>

      <div>
        <label htmlFor="owner_name">Owner name</label>
        <input
          id="owner_name"
          value={form.owner_name}
          onChange={(e) => handleChange("owner_name", e.target.value)}
          aria-describedby={fieldErrors.owner_name ? "owner_name-error" : undefined}
        />
        {fieldErrors.owner_name && (
          <span id="owner_name-error" role="alert">
            {fieldErrors.owner_name}
          </span>
        )}
      </div>

      {conflict && <p role="alert">{conflict}</p>}

      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? "Provisioning…" : "Provision tenant"}
      </button>

      {lastResult && (
        <p role="status">
          Provisioned — tenant {lastResult.tenant_id}, owner {lastResult.owner_id}
        </p>
      )}
    </form>
  );
}

export default function ProvisioningPage() {
  const qc = useQueryClient();

  const { data: me, isLoading: meLoading } = useQuery({
    queryKey: ["platform-me"],
    queryFn: () => api.get<PlatformMe>("/platform/me"),
  });

  const permissions = me?.permissions ?? [];
  const hasProvision = permissions.includes(PERM_PROVISION);

  const { data: tenants = [] } = useQuery({
    queryKey: ["platform-tenants"],
    queryFn: () => api.get<TenantListItem[]>("/platform/tenants"),
    enabled: hasProvision,
  });

  if (meLoading) return <p>Loading…</p>;

  if (!hasProvision) {
    return (
      <section aria-label="Provisioning">
        <h1>Provisioning</h1>
        <p>Your operator account does not have the provisioning permission.</p>
      </section>
    );
  }

  return (
    <section aria-label="Provisioning">
      <h1>Provisioning</h1>

      <section aria-label="Tenant list">
        <h2>Tenants</h2>
        <TenantList tenants={tenants} />
      </section>

      <section aria-label="Provision new tenant">
        <h2>Provision a new tenant</h2>
        <ProvisionForm
          onSuccess={() => {}}
          onPermissionLost={() => qc.invalidateQueries({ queryKey: ["platform-me"] })}
        />
      </section>
    </section>
  );
}
