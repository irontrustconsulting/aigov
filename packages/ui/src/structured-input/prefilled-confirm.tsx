import { Button } from "../primitives/button";

/** FE-4: top of the input-preference order — a prefilled value the user
 * confirms with one action, no typing required. */
export function PrefilledConfirm({
  valueLabel,
  onConfirm,
}: {
  valueLabel: string;
  onConfirm: () => void;
}) {
  return (
    <div>
      <span>{valueLabel}</span>
      <Button type="button" onClick={onConfirm}>
        Confirm
      </Button>
    </div>
  );
}
