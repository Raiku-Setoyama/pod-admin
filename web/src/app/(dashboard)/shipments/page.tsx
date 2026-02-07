"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/layout/page-container";
import { Pagination } from "@/components/common/pagination";
import { PageLoading } from "@/components/common/loading-spinner";
import { ShipmentList } from "@/features/shipments/components/shipment-list";
import { ShipmentFilters } from "@/features/shipments/components/shipment-filters";
import { useShipments } from "@/features/shipments/hooks/use-shipments";
import type { Shipment, ShipmentStatus } from "@/types/api";

type SortBy = "created_at" | "shipped_at" | "delivered_at";
type SortOrder = "asc" | "desc";

export default function ShipmentsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);

  // Filter states
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ShipmentStatus | null>(null);
  const [trackingNumber, setTrackingNumber] = useState("");
  const [carrier, setCarrier] = useState<string | null>(null);
  const [shippedFrom, setShippedFrom] = useState("");
  const [shippedTo, setShippedTo] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [deliveredFrom, setDeliveredFrom] = useState("");
  const [deliveredTo, setDeliveredTo] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("created_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  const { shipments, total, isLoading } = useShipments({
    page,
    limit,
    status,
    search: search || undefined,
    tracking_number: trackingNumber || undefined,
    carrier: carrier || undefined,
    shipped_from: shippedFrom || undefined,
    shipped_to: shippedTo || undefined,
    created_from: createdFrom || undefined,
    created_to: createdTo || undefined,
    delivered_from: deliveredFrom || undefined,
    delivered_to: deliveredTo || undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  const handleRowClick = (shipment: Shipment) => {
    router.push(`/shipments/${shipment.id}`);
  };

  const handleReset = () => {
    setSearch("");
    setStatus(null);
    setTrackingNumber("");
    setCarrier(null);
    setShippedFrom("");
    setShippedTo("");
    setCreatedFrom("");
    setCreatedTo("");
    setDeliveredFrom("");
    setDeliveredTo("");
    setSortBy("created_at");
    setSortOrder("desc");
    setPage(1);
  };

  const handleSortChange = (newSortBy: SortBy, newSortOrder: SortOrder) => {
    setSortBy(newSortBy);
    setSortOrder(newSortOrder);
    setPage(1);
  };

  return (
    <PageContainer
      title="配送一覧"
      description="配送管理・追跡情報"
      actions={
        <div className="flex gap-2">
          <Button variant="outline">
            <Upload className="h-4 w-4" />
            伝票番号インポート
          </Button>
          <Button>
            <Plus className="h-4 w-4" />
            新規配送
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <ShipmentFilters
          search={search}
          status={status}
          trackingNumber={trackingNumber}
          carrier={carrier}
          shippedFrom={shippedFrom}
          shippedTo={shippedTo}
          createdFrom={createdFrom}
          createdTo={createdTo}
          deliveredFrom={deliveredFrom}
          deliveredTo={deliveredTo}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSearchChange={(value) => { setSearch(value); setPage(1); }}
          onStatusChange={(value) => { setStatus(value); setPage(1); }}
          onTrackingNumberChange={(value) => { setTrackingNumber(value); setPage(1); }}
          onCarrierChange={(value) => { setCarrier(value); setPage(1); }}
          onShippedFromChange={(value) => { setShippedFrom(value); setPage(1); }}
          onShippedToChange={(value) => { setShippedTo(value); setPage(1); }}
          onCreatedFromChange={(value) => { setCreatedFrom(value); setPage(1); }}
          onCreatedToChange={(value) => { setCreatedTo(value); setPage(1); }}
          onDeliveredFromChange={(value) => { setDeliveredFrom(value); setPage(1); }}
          onDeliveredToChange={(value) => { setDeliveredTo(value); setPage(1); }}
          onSortChange={handleSortChange}
          onReset={handleReset}
        />

        {isLoading ? (
          <PageLoading />
        ) : (
          <>
            <ShipmentList shipments={shipments} onRowClick={handleRowClick} />
            <Pagination
              page={page}
              limit={limit}
              total={total}
              onPageChange={setPage}
              onLimitChange={(newLimit) => {
                setLimit(newLimit);
                setPage(1);
              }}
            />
          </>
        )}
      </div>
    </PageContainer>
  );
}
