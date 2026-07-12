/**
 * @jest-environment jsdom
 */
import { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { GroupedMultiSelect, type GroupedMultiSelectOption } from "../grouped-multi-select";

const mixedOptions: GroupedMultiSelectOption[] = [
  { value: "health", label: "Health Data", group: "duty" },
  { value: "genetic", label: "Genetic Data", group: "duty" },
  { value: "identifiers", label: "Identifiers", group: "other" },
  { value: "contact_details", label: "Contact Details", group: "other" },
];

function ControlledGroupedMultiSelect({ options }: { options: GroupedMultiSelectOption[] }) {
  const [values, setValues] = useState<string[]>([]);
  return (
    <GroupedMultiSelect
      id="data-categories"
      label="Data categories"
      values={values}
      options={options}
      onChange={setValues}
      dutyHeading="Special-category data"
      dutyCaption="GDPR Art. 9, heightened duty"
      otherHeading="Other personal data"
    />
  );
}

describe("GroupedMultiSelect", () => {
  test("partitions options into duty vs other subgroups by the group field", () => {
    render(<ControlledGroupedMultiSelect options={mixedOptions} />);
    // dutyHeading appears twice: the custom heading paragraph and the reused MultiSelectInput legend
    expect(screen.getAllByText("Special-category data").length).toBeGreaterThan(0);
    expect(screen.getByText("GDPR Art. 9, heightened duty")).toBeInTheDocument();
    expect(screen.getByText("Health Data")).toBeInTheDocument();
    expect(screen.getByText("Genetic Data")).toBeInTheDocument();
    expect(screen.getByText("Identifiers")).toBeInTheDocument();
    expect(screen.getByText("Contact Details")).toBeInTheDocument();
  });

  test("toggling a chip in either subgroup updates the single shared values array", () => {
    render(<ControlledGroupedMultiSelect options={mixedOptions} />);

    const healthCheckbox = screen.getByRole("checkbox", { name: "Health Data" });
    fireEvent.click(healthCheckbox);
    expect(healthCheckbox).toBeChecked();

    const identifiersCheckbox = screen.getByRole("checkbox", { name: "Identifiers" });
    fireEvent.click(identifiersCheckbox);
    expect(identifiersCheckbox).toBeChecked();
    // both selections coexist in the one shared array
    expect(healthCheckbox).toBeChecked();
  });

  test("an all-other option set renders no duty heading", () => {
    const allOther: GroupedMultiSelectOption[] = [
      { value: "identifiers", label: "Identifiers", group: "other" },
      { value: "contact_details", label: "Contact Details", group: "other" },
    ];
    render(<ControlledGroupedMultiSelect options={allOther} />);
    expect(screen.queryByText("Special-category data")).not.toBeInTheDocument();
    expect(screen.queryByText("GDPR Art. 9, heightened duty")).not.toBeInTheDocument();
    expect(screen.getByText("Identifiers")).toBeInTheDocument();
  });

  test("an all-duty option set renders no other heading and no other chips", () => {
    const allDuty: GroupedMultiSelectOption[] = [
      { value: "health", label: "Health Data", group: "duty" },
    ];
    render(<ControlledGroupedMultiSelect options={allDuty} />);
    expect(screen.getAllByText("Special-category data").length).toBeGreaterThan(0);
    expect(screen.queryByText("Contact Details")).not.toBeInTheDocument();
  });

  test("rendered DOM carries no --verdict-* class and no border-brand on the subgroup rule", () => {
    const { container } = render(<ControlledGroupedMultiSelect options={mixedOptions} />);
    const html = container.innerHTML;
    expect(html).not.toMatch(/--verdict-/);
    expect(html).not.toMatch(/border-brand/);
  });
});
