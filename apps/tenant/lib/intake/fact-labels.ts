/** Curated display labels for live catalogue_fact keys. A1=a (D-60, R2). */
export const FACT_LABELS: Record<string, string> = {
  bias_audit: "Bias audit",
  bias_testing: "Bias testing",
  certifications: "Certifications",
  content_credentials: "Content credentials",
  content_policy: "Content policy",
  data_deletion: "Data deletion",
  data_residency: "Data residency",
  data_retention: "Data retention",
  data_retention_default: "Data retention default",
  deepfake_policy: "Deepfake policy",
  deployment_options: "Deployment options",
  dpa_available: "DPA available",
  eea_entity: "EEA contracting entity",
  encryption_at_rest: "Encryption at rest",
  encryption_in_transit: "Encryption in transit",
  enterprise_privacy_mode: "Enterprise privacy mode",
  model_family: "Model family",
  regulatory_note: "Regulatory note",
  responsible_ai_standard: "Responsible AI standard",
  sso_saml_available: "SSO / SAML available",
  sub_processors_listed: "Sub-processors listed",
  synthetic_content_marking: "Synthetic content marking",
  training_data_note: "Training data note",
  training_data_provenance: "Training data provenance",
  trains_on_customer_data: "Trains on customer data",
  trust_layer_features: "Trust layer features",
  voice_cloning_consent: "Voice cloning consent",
};

/** Replace underscores with spaces and capitalise the first word. */
function humanise(key: string): string {
  const spaced = key.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** Returns the curated label for a fact key, falling back to humanise on a miss.
 * Warns on miss so new keys are surfaced during development (mirrors D-60). */
export function labelForFactKey(key: string): string {
  const label = FACT_LABELS[key];
  if (label !== undefined) return label;
  // eslint-disable-next-line no-console
  console.warn(`[labelForFactKey] No curated label for fact key "${key}" — add it to FACT_LABELS.`);
  return humanise(key);
}
