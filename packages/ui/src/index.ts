export { AppShell, type AppShellProps } from "./shell/app-shell";
export { Sidebar, type SidebarProps, type SidebarNavItem } from "./shell/sidebar";

export { PageHeader, type PageHeaderProps } from "./scaffold/page-header";
export { PageScaffold, type PageScaffoldProps } from "./scaffold/page-scaffold";
export { SectionGroup, type SectionGroupProps } from "./scaffold/section-group";

export { EmptyState, type EmptyStateProps } from "./state/empty-state";
export { FirstRunPanel, type FirstRunPanelProps } from "./state/first-run-panel";
export { ErrorState, type ErrorStateProps } from "./state/error-state";
export { Skeleton, SkeletonBlock } from "./state/skeleton";

export { LogoTile, type LogoTileProps } from "./kit/logo-tile";
export { ResumePrompt, type ResumePromptProps } from "./kit/resume-prompt";
export { DraftResumeIndicator, type DraftResumeIndicatorProps } from "./kit/draft-resume-indicator";
export { StatCard, type StatCardProps } from "./kit/stat-card";
export { SectionHeader, type SectionHeaderProps } from "./kit/section-header";
export { ListSelectRow, type ListSelectRowProps } from "./kit/list-select-row";
export {
  DataTable,
  DataTableHeader,
  DataTableBody,
  type DataTableProps,
  type DataTableHeaderProps,
  type DataTableBodyProps,
} from "./kit/data-table";

export { Button, type ButtonProps, type ButtonVariant } from "./primitives/button";
export { Select } from "./primitives/select";
export { Dialog } from "./primitives/dialog";
export {
  Table,
  TableBody,
  TableHeaderRow,
  TableRow,
  TableCell,
  TableHeaderCell,
  type TableDensity,
} from "./primitives/table";
export { QueueRow, type QueueRowDensity } from "./primitives/queue-row";

export { PrefilledConfirm } from "./structured-input/prefilled-confirm";
export { SingleSelect, type SelectOption } from "./structured-input/single-select";
export { MultiSelectInput } from "./structured-input/multi-select-input";
export {
  ConstrainedNumberInput,
  ConstrainedDateInput,
} from "./structured-input/constrained-structured";
export { FreeText } from "./structured-input/free-text";
export { TextInput } from "./structured-input/text-input";

export {
  PrefillWithBasis,
  type PrefillWithBasisProps,
  type StructuredOption,
} from "./prefill-with-basis/prefill-with-basis";
export { ProvenanceBadge, type Provenance } from "./prefill-with-basis/provenance-badge";

export { SodAction, type SodActionProps } from "./sod-wrapper/sod-action";

export { StaleLockBanner } from "./concurrency/stale-lock-banner";
export { BadFromStateBanner } from "./concurrency/bad-from-state-banner";

export { WhoseCourtIndicator } from "./status/whose-court-indicator";
export { VerdictChip, type VerdictTone } from "./status/verdict-chip";
export { TierBadge, toTierMember, type TierMember, type TierBadgeProps } from "./status/tier-badge";

export { EvidenceTable, type EvidenceRow } from "./evidence/evidence-table";
export { EvidenceUploadControl } from "./evidence/evidence-upload-control";
export { EvidenceLinkPicker, type EvidencePickerRow } from "./evidence/evidence-link-picker";
export { EvidenceManifestChip, type ManifestLink } from "./evidence/evidence-manifest-chip";

export { CoverageMatrix } from "./audit/coverage-matrix";
export { NotAnObligationSetBanner } from "./audit/not-an-obligation-set-banner";
export { AuditGradeDivider } from "./audit/audit-grade-divider";
export { AuditPackView } from "./audit/audit-pack-view";
export { EvidenceManifestTable } from "./audit/evidence-manifest-table";
export { AtoDocumentView } from "./audit/ato-document-view";
