export const evidenceKeys = {
  list: () => ["evidence-list"] as const,
  detail: (id: string) => ["evidence-detail", id] as const,
} as const;
