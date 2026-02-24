"use client";

import { OrderSourceList } from "@/features/order-sources/components/order-source-list";

export default function OrderSourcesPage() {
  return (
    <div className="container mx-auto py-6">
      <OrderSourceList />
    </div>
  );
}
