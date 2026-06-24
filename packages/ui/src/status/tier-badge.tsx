/**
 * INV-64: eu_ai_act_tier renders ONLY via TierBadge.
 * Four magnitude tiers on --tier-* channel (D-48/FE-16 amended).
 * Two resolution states (UNCLASSIFIED, REQUIRES_CONTEXT) on --verdict-*
 * because they are verdict-class, not magnitudes.
 * No VerdictChip renders any tier member; no TierBadge renders any non-tier member.
 */
import { Ban } from "lucide-react";

export type TierMember =
  | "PROHIBITED"
  | "HIGH"
  | "LIMITED"
  | "MINIMAL"
  | "UNCLASSIFIED"
  | "REQUIRES_CONTEXT";

export interface TierBadgeProps {
  value: TierMember;
  variant?: "compact" | "card";
  /** Card only — basis/annex/criteria text rendered beneath the tier hero. */
  basis?: React.ReactNode;
  /** Card only — caller provides the SodAction-gated override form; absent for non-system_owner. */
  overrideLadder?: React.ReactNode;
}

type TierStyle = {
  style: React.CSSProperties;
  className: string;
};

const TIER_STYLES: Record<TierMember, TierStyle> = {
  PROHIBITED: {
    className: "rounded-sm px-2 py-0.5 text-xs font-medium",
    style: {
      backgroundColor: "var(--tier-prohibited-fill)",
      color: "var(--tier-prohibited-text)",
    },
  },
  HIGH: {
    className: "rounded-sm px-2 py-0.5 text-xs font-medium",
    style: {
      backgroundColor: "var(--tier-high-fill)",
      color: "var(--tier-high-text)",
    },
  },
  LIMITED: {
    className: "rounded-sm border px-2 py-0.5 text-xs font-medium",
    style: {
      backgroundColor: "var(--tier-limited-fill)",
      color: "var(--tier-limited-text)",
      borderColor: "var(--tier-limited-text)",
    },
  },
  MINIMAL: {
    className: "rounded-sm border px-2 py-0.5 text-xs font-medium",
    style: {
      backgroundColor: "var(--tier-minimal-fill)",
      color: "var(--tier-minimal-text)",
      borderColor: "var(--tier-minimal-text)",
    },
  },
  UNCLASSIFIED: {
    className: "rounded-sm border px-2 py-0.5 text-xs font-medium",
    style: {
      borderColor: "var(--verdict-neutral)",
      color: "var(--verdict-neutral)",
    },
  },
  REQUIRES_CONTEXT: {
    className: "rounded-sm border px-2 py-0.5 text-xs font-medium",
    style: {
      borderColor: "var(--verdict-attention)",
      color: "var(--verdict-attention)",
    },
  },
};

const MAGNITUDE_TIERS = new Set<TierMember>(["PROHIBITED", "HIGH", "LIMITED", "MINIMAL"]);

/** Maps the wire-format EUAIActTier snake_case value to the display TierMember. */
const EU_TIER_TO_MEMBER: Record<string, TierMember> = {
  prohibited: "PROHIBITED",
  high_risk: "HIGH",
  limited_risk: "LIMITED",
  minimal_risk: "MINIMAL",
  unclassified: "UNCLASSIFIED",
  requires_context: "REQUIRES_CONTEXT",
};

/** Converts an EUAIActTier wire value (e.g. "high_risk") to the TierMember
 * display value (e.g. "HIGH"). Falls back to uppercase if the value is not
 * in the map (handles callers that already pass TierMember-style values). */
export function toTierMember(euTier: string): TierMember {
  return EU_TIER_TO_MEMBER[euTier] ?? (euTier.toUpperCase() as TierMember);
}

export function TierBadge({
  value,
  variant = "compact",
  basis,
  overrideLadder,
}: TierBadgeProps) {
  const { className, style } = TIER_STYLES[value];
  const isMagnitude = MAGNITUDE_TIERS.has(value);

  if (variant === "compact") {
    return (
      <span
        data-tier={value.toLowerCase()}
        data-variant="compact"
        data-tier-channel={isMagnitude ? "tier" : "verdict"}
        className={className}
        style={style}
      >
        {value === "PROHIBITED" && (
          <Ban
            size={12}
            aria-hidden="true"
            className="mr-1 inline-block align-text-bottom"
          />
        )}
        {value}
      </span>
    );
  }

  return (
    <div
      data-tier={value.toLowerCase()}
      data-variant="card"
      className="rounded-lg border p-4"
      style={{
        borderColor: isMagnitude ? "var(--color-hairline)" : style.borderColor ?? "var(--color-hairline)",
        backgroundColor: isMagnitude ? (style.backgroundColor ?? "transparent") : undefined,
      }}
    >
      <div className="mb-2 flex items-center gap-2">
        {value === "PROHIBITED" && (
          <Ban
            size={16}
            aria-hidden="true"
            style={{ color: "var(--tier-prohibited-text)" }}
          />
        )}
        <span
          data-tier-hero
          className="text-lg font-semibold"
          style={{ color: style.color }}
        >
          {value}
        </span>
      </div>
      {basis && (
        <div className="text-ink-secondary mb-3 text-sm">{basis}</div>
      )}
      {overrideLadder && (
        <div className="mt-3 border-t pt-3" style={{ borderColor: "var(--color-hairline)" }}>
          {overrideLadder}
        </div>
      )}
    </div>
  );
}
