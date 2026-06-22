export const auditKeys = {
  tenantCoverage: (framework?: string, includeUnapproved?: boolean) =>
    ["audit-coverage-tenant", framework, includeUnapproved] as const,
  systemCoverage: (systemId: string, framework?: string, includeUnapproved?: boolean) =>
    ["audit-coverage-system", systemId, framework, includeUnapproved] as const,
  useCaseCoverage: (assessmentId: string, framework?: string, includeUnapproved?: boolean) =>
    ["audit-coverage-usecase", assessmentId, framework, includeUnapproved] as const,
  systemExport: (systemId: string, framework?: string) =>
    ["audit-export-system", systemId, framework] as const,
  useCaseExport: (useCaseId: string, framework?: string) =>
    ["audit-export-usecase", useCaseId, framework] as const,
  frameworkExport: (framework: string) =>
    ["audit-export-framework", framework] as const,
  atoDocument: (useCaseId: string, round?: number) =>
    ["audit-ato-document", useCaseId, round] as const,
} as const;
