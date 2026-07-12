"use client";

import { useState } from "react";
import {
  SectionGroup,
  DataTable,
  DataTableHeader,
  DataTableBody,
  TableRow,
  TableCell,
  TableHeaderCell,
  Skeleton,
  ErrorState,
  EmptyState,
  VerdictChip,
  SodAction,
  Button,
} from "@irontrust/ui";
import type { ProductClearanceEntry, VendorClearanceEntry } from "@irontrust/api-client";
import { useClearanceQueue } from "@/lib/clearances";
import { ClearanceDialog, type ClearanceTarget } from "./clearance-dialog";

interface ClearanceQueueListProps {
  isAuthoriser: boolean;
}

function formatDate(iso: string | null): string | null {
  return iso ? new Date(iso).toLocaleDateString() : null;
}

function DecidedBy({
  name,
  decidedAt,
}: {
  name: string | null;
  decidedAt: string | null;
}) {
  if (!name) {
    return <span className="text-ink-muted text-xs">Not yet decided</span>;
  }
  const date = formatDate(decidedAt);
  return (
    <span className="text-ink-muted text-xs">
      {name}
      {date ? ` · ${date}` : null}
    </span>
  );
}

export function ClearanceQueueList({ isAuthoriser }: ClearanceQueueListProps) {
  const queueQuery = useClearanceQueue();
  const [target, setTarget] = useState<ClearanceTarget | null>(null);

  if (queueQuery.isLoading) {
    return <Skeleton lines={4} />;
  }

  if (queueQuery.isError) {
    return (
      <ErrorState message="Could not load the clearance queue." onRetry={() => queueQuery.refetch()} />
    );
  }

  const vendors = queueQuery.data?.vendors ?? [];

  if (vendors.length === 0) {
    return <EmptyState message="No vendors or products are currently awaiting clearance." />;
  }

  return (
    <>
      <div className="space-y-6">
        {vendors.map((vendor) => (
          <VendorSection
            key={vendor.catalogue_vendor_id}
            vendor={vendor}
            isAuthoriser={isAuthoriser}
            onSetClearance={setTarget}
          />
        ))}
      </div>

      {target && (
        <ClearanceDialog
          target={target}
          open={Boolean(target)}
          onClose={() => setTarget(null)}
        />
      )}
    </>
  );
}

function VendorSection({
  vendor,
  isAuthoriser,
  onSetClearance,
}: {
  vendor: VendorClearanceEntry;
  isAuthoriser: boolean;
  onSetClearance: (target: ClearanceTarget) => void;
}) {
  const vendorCleared = vendor.status === "approved";

  return (
    <SectionGroup title={vendor.vendor_name}>
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <VerdictChip value={vendor.status} />
              <span className="text-ink-muted text-xs">
                {vendor.awaiting_use_case_count} awaiting clearance · {vendor.affected_use_case_count}{" "}
                use case{vendor.affected_use_case_count === 1 ? "" : "s"} across{" "}
                {vendor.affected_system_count} system{vendor.affected_system_count === 1 ? "" : "s"} will
                be re-evaluated
              </span>
            </div>
            <DecidedBy name={vendor.decided_by_name} decidedAt={vendor.decided_at} />
            {vendor.note && <p className="text-ink-muted text-xs">{vendor.note}</p>}
          </div>
          <SodAction barred={!isAuthoriser}>
            <Button
              variant="secondary"
              onClick={() =>
                onSetClearance({
                  kind: "vendor",
                  id: vendor.catalogue_vendor_id,
                  name: vendor.vendor_name,
                  status: vendor.status,
                  validUntil: vendor.valid_until,
                  note: vendor.note,
                  affectedUseCaseCount: vendor.affected_use_case_count,
                  affectedSystemCount: vendor.affected_system_count,
                })
              }
            >
              Set clearance
            </Button>
          </SodAction>
        </div>

        {vendor.products.length > 0 && (
          <DataTable density="compact">
            <DataTableHeader>
              <TableHeaderCell>Product</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Decided by</TableHeaderCell>
              <TableHeaderCell>{""}</TableHeaderCell>
            </DataTableHeader>
            <DataTableBody>
              {vendor.products.map((product) => (
                <ProductRow
                  key={product.catalogue_product_id}
                  product={product}
                  vendorCleared={vendorCleared}
                  isAuthoriser={isAuthoriser}
                  onSetClearance={onSetClearance}
                />
              ))}
            </DataTableBody>
          </DataTable>
        )}
      </div>
    </SectionGroup>
  );
}

function ProductRow({
  product,
  vendorCleared,
  isAuthoriser,
  onSetClearance,
}: {
  product: ProductClearanceEntry;
  vendorCleared: boolean;
  isAuthoriser: boolean;
  onSetClearance: (target: ClearanceTarget) => void;
}) {
  return (
    <TableRow>
      <TableCell>
        <div className="space-y-0.5">
          <span>{product.product_name}</span>
          <p className="text-ink-muted text-xs">
            {product.awaiting_use_case_count} awaiting · {product.affected_use_case_count} use case
            {product.affected_use_case_count === 1 ? "" : "s"} across {product.affected_system_count}{" "}
            system{product.affected_system_count === 1 ? "" : "s"}
          </p>
          {product.note && <p className="text-ink-muted text-xs">{product.note}</p>}
        </div>
      </TableCell>
      <TableCell>
        <VerdictChip value={product.status} />
      </TableCell>
      <TableCell>
        <DecidedBy name={product.decided_by_name} decidedAt={product.decided_at} />
      </TableCell>
      <TableCell>
        <SodAction
          barred={!isAuthoriser}
          blockedReason={vendorCleared ? null : "Clear the vendor first"}
        >
          <Button
            variant="secondary"
            onClick={() =>
              onSetClearance({
                kind: "product",
                id: product.catalogue_product_id,
                name: product.product_name,
                status: product.status,
                validUntil: product.valid_until,
                note: product.note,
                affectedUseCaseCount: product.affected_use_case_count,
                affectedSystemCount: product.affected_system_count,
              })
            }
          >
            Set clearance
          </Button>
        </SodAction>
      </TableCell>
    </TableRow>
  );
}
