import { FACT_LABELS, labelForFactKey } from "../fact-labels";

describe("FACT_LABELS dictionary", () => {
  test("covers all 27 live fact keys (no underscore in output for any)", () => {
    const liveKeys = [
      "bias_audit", "bias_testing", "certifications", "content_credentials",
      "content_policy", "data_deletion", "data_residency", "data_retention",
      "data_retention_default", "deepfake_policy", "deployment_options",
      "dpa_available", "eea_entity", "encryption_at_rest", "encryption_in_transit",
      "enterprise_privacy_mode", "model_family", "regulatory_note",
      "responsible_ai_standard", "sso_saml_available", "sub_processors_listed",
      "synthetic_content_marking", "training_data_note", "training_data_provenance",
      "trains_on_customer_data", "trust_layer_features", "voice_cloning_consent",
    ];
    for (const key of liveKeys) {
      const label = FACT_LABELS[key];
      expect(label).toBeDefined();
      expect(label).not.toContain("_");
    }
  });

  test("acronym-critical keys have correct labels", () => {
    expect(FACT_LABELS["dpa_available"]).toBe("DPA available");
    expect(FACT_LABELS["eea_entity"]).toBe("EEA contracting entity");
    expect(FACT_LABELS["sso_saml_available"]).toBe("SSO / SAML available");
    expect(FACT_LABELS["responsible_ai_standard"]).toBe("Responsible AI standard");
  });
});

describe("labelForFactKey", () => {
  test("known key → returns dictionary label", () => {
    expect(labelForFactKey("dpa_available")).toBe("DPA available");
    expect(labelForFactKey("trains_on_customer_data")).toBe("Trains on customer data");
    expect(labelForFactKey("certifications")).toBe("Certifications");
  });

  test("unknown key → humanised label + console.warn fires once", () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const result = labelForFactKey("some_new_fact_key");
    expect(result).toBe("Some new fact key");
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("some_new_fact_key")
    );
    warnSpy.mockRestore();
  });

  test("no underscore reaches output for any live key", () => {
    const liveKeys = Object.keys(FACT_LABELS);
    for (const key of liveKeys) {
      expect(labelForFactKey(key)).not.toContain("_");
    }
  });
});
