/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import { FactValue } from "../fact-value";

describe("FactValue §3 branches", () => {
  // Branch 1 — boolean answer
  test("{answer:true, note} → Yes chip + note, no JSON", () => {
    const { container } = render(
      <FactValue value={{ answer: true, note: "Confirmed by vendor." }} />
    );
    const chip = container.querySelector("[data-bool='true']");
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveTextContent("Yes");
    expect(screen.getByText("Confirmed by vendor.")).toBeInTheDocument();
    expect(container.textContent).not.toContain("{");
    expect(container.textContent).not.toContain("JSON");
  });

  test("{answer:false, note} → No chip + note", () => {
    const { container } = render(
      <FactValue value={{ answer: false, note: "Not applicable." }} />
    );
    const chip = container.querySelector("[data-bool='false']");
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveTextContent("No");
    expect(screen.getByText("Not applicable.")).toBeInTheDocument();
  });

  test("{answer:true, url} → Yes chip + Source anchor", () => {
    render(<FactValue value={{ answer: true, url: "https://example.com/dpa" }} />);
    expect(screen.getByRole("link", { name: "Source" })).toHaveAttribute(
      "href",
      "https://example.com/dpa"
    );
  });

  // Branch 2 — array-valued key
  test("{list:[a,b,c]} → 3 pills, no comma-join string in DOM", () => {
    const { container } = render(
      <FactValue value={{ list: ["SOC 2", "ISO 27001", "GDPR"] }} />
    );
    const pills = container.querySelectorAll("[data-fact-value]");
    expect(pills).toHaveLength(3);
    expect(screen.getByText("SOC 2")).toBeInTheDocument();
    expect(screen.getByText("ISO 27001")).toBeInTheDocument();
    expect(screen.getByText("GDPR")).toBeInTheDocument();
    expect(container.textContent).not.toContain("SOC 2,ISO 27001");
  });

  test("{regions:[…], note} → pills + note", () => {
    const { container } = render(
      <FactValue value={{ regions: ["EU", "US"], note: "Configurable." }} />
    );
    const pills = container.querySelectorAll("[data-fact-value]");
    expect(pills).toHaveLength(2);
    expect(screen.getByText("Configurable.")).toBeInTheDocument();
  });

  test("{models:[…]} → pills", () => {
    const { container } = render(
      <FactValue value={{ models: ["Claude 3.5 Sonnet", "GPT-4o"] }} />
    );
    expect(container.querySelectorAll("[data-fact-value]")).toHaveLength(2);
  });

  test("{features:[…]} → pills via any-array-key fallback", () => {
    const { container } = render(
      <FactValue value={{ features: ["Dynamic Grounding", "PII Masking"] }} />
    );
    expect(container.querySelectorAll("[data-fact-value]")).toHaveLength(2);
  });

  test("{options:[…]} → pills via any-array-key fallback", () => {
    const { container } = render(
      <FactValue value={{ options: ["Cloud", "On-premise"] }} />
    );
    expect(container.querySelectorAll("[data-fact-value]")).toHaveLength(2);
  });

  // Branch 3 — string-valued key
  test("{standard} → plain text", () => {
    render(<FactValue value={{ standard: "ISO 27001" }} />);
    expect(screen.getByText("ISO 27001")).toBeInTheDocument();
  });

  test("{entity, note} → plain text + note", () => {
    render(<FactValue value={{ entity: "EU entity", note: "Registered in Ireland." }} />);
    expect(screen.getByText("EU entity")).toBeInTheDocument();
    expect(screen.getByText("Registered in Ireland.")).toBeInTheDocument();
  });

  test("{framework, note} → plain text + note", () => {
    render(<FactValue value={{ framework: "NIST AI RMF", note: "Aligned." }} />);
    expect(screen.getByText("NIST AI RMF")).toBeInTheDocument();
    expect(screen.getByText("Aligned.")).toBeInTheDocument();
  });

  // Branch 4 — note only
  test("{note} → note text as value", () => {
    render(<FactValue value={{ note: "Built on Anthropic Claude models with law-specific fine-tuning." }} />);
    expect(
      screen.getByText("Built on Anthropic Claude models with law-specific fine-tuning.")
    ).toBeInTheDocument();
  });

  // Branch 5 — residual (definition list, no JSON.stringify)
  test("{days, note} → definition list + note, no JSON.stringify substring in DOM", () => {
    const { container } = render(
      <FactValue
        value={{
          days: 30,
          note: "API data retained up to 30 days for abuse monitoring.",
        }}
      />
    );
    expect(screen.getByText("days:")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(
      screen.getByText("API data retained up to 30 days for abuse monitoring.")
    ).toBeInTheDocument();
    // No JSON.stringify artefact
    expect(container.textContent).not.toMatch(/\{.*".*":.*\}/);
    expect(container.textContent).not.toContain("JSON.stringify");
  });

  // Guardrails — no verdict/tone attributes on any element
  test("no element carries data-tone or --verdict-* attribute", () => {
    const { container } = render(
      <FactValue value={{ answer: true, note: "Vendor confirmed." }} />
    );
    const allElements = container.querySelectorAll("*");
    allElements.forEach((el) => {
      expect(el).not.toHaveAttribute("data-tone");
      const style = (el as HTMLElement).getAttribute("style") ?? "";
      expect(style).not.toContain("--verdict-");
    });
  });
});
