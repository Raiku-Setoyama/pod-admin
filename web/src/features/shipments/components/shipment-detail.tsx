"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/common/status-badge";
import { PackingPhotoUpload } from "./packing-photo-upload";
import { Truck, Package, MapPin } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import type { Shipment, ShipmentStatus } from "@/types/api";

interface ShipmentDetailProps {
  shipment: Shipment;
  onUpdate?: () => void;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const statusOptions: { value: ShipmentStatus; label: string }[] = [
  { value: "pending", label: "配送準備中" },
  { value: "ready", label: "準備完了" },
  { value: "shipped", label: "発送完了" },
];

export function ShipmentDetail({ shipment, onUpdate }: ShipmentDetailProps) {
  const [isStatusDialogOpen, setIsStatusDialogOpen] = useState(false);
  const [newStatus, setNewStatus] = useState<ShipmentStatus>(shipment.status);
  const [trackingNumber, setTrackingNumber] = useState(shipment.tracking_number || "");
  const [isUpdating, setIsUpdating] = useState(false);

  const handleStatusUpdate = async () => {
    setIsUpdating(true);
    try {
      await apiClient(`/shipments/${shipment.id}/status`, {
        method: "PATCH",
        body: {
          status: newStatus,
          tracking_number: trackingNumber || undefined,
        },
      });
      setIsStatusDialogOpen(false);
      onUpdate?.();
    } catch (error) {
      console.error("Status update failed:", error);
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 配送情報 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Truck className="h-5 w-5" />
              配送情報
            </CardTitle>
            <div className="flex items-center gap-3">
              <StatusBadge status={shipment.status} />
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsStatusDialogOpen(true)}
              >
                ステータス更新
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-sm text-muted-foreground">配送ID</dt>
              <dd className="font-medium">{shipment.id.slice(0, 8)}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">作成日時</dt>
              <dd className="font-medium">{formatDate(shipment.created_at)}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">運送会社</dt>
              <dd className="font-medium">{shipment.carrier || "-"}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">伝票番号</dt>
              <dd className="font-medium">{shipment.tracking_number || "-"}</dd>
            </div>
            {shipment.shipped_at && (
              <div>
                <dt className="text-sm text-muted-foreground">発送日時</dt>
                <dd className="font-medium">{formatDate(shipment.shipped_at)}</dd>
              </div>
            )}
            {shipment.delivered_at && (
              <div>
                <dt className="text-sm text-muted-foreground">配送完了予定日時</dt>
                <dd className="font-medium">{formatDate(shipment.delivered_at)}</dd>
              </div>
            )}
            {shipment.note && (
              <div className="col-span-2">
                <dt className="text-sm text-muted-foreground">備考</dt>
                <dd className="font-medium">{shipment.note}</dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>

      {/* 配送先情報 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" />
            配送先
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-sm text-muted-foreground">氏名</dt>
              <dd className="font-medium">{shipment.customer_name}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">電話番号</dt>
              <dd className="font-medium">{shipment.customer_phone || "-"}</dd>
            </div>
            <div className="col-span-2">
              <dt className="text-sm text-muted-foreground">住所</dt>
              <dd className="font-medium">
                〒{shipment.customer_postal_code}
                <br />
                {shipment.customer_full_address}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* 梱包写真 */}
      <PackingPhotoUpload
        shipmentId={shipment.id}
        currentPhotoPath={shipment.packing_photo_path}
        onUploadComplete={onUpdate}
      />

      {/* 含まれる商品一覧 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            含まれる商品 ({shipment.items.length}件)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>注文番号</TableHead>
                <TableHead>商品名</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shipment.items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">
                    {item.order_number || "-"}
                  </TableCell>
                  <TableCell>{item.product_name || "-"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* ステータス更新ダイアログ */}
      <Dialog open={isStatusDialogOpen} onOpenChange={setIsStatusDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>ステータス更新</DialogTitle>
            <DialogDescription>
              配送のステータスを更新します。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">新しいステータス</label>
              <Select
                value={newStatus}
                onValueChange={(value) => setNewStatus(value as ShipmentStatus)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {newStatus === "shipped" && (
              <div className="space-y-2">
                <label className="text-sm font-medium">伝票番号</label>
                <Input
                  placeholder="伝票番号を入力"
                  value={trackingNumber}
                  onChange={(e) => setTrackingNumber(e.target.value)}
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsStatusDialogOpen(false)}
            >
              キャンセル
            </Button>
            <Button onClick={handleStatusUpdate} disabled={isUpdating}>
              {isUpdating ? "更新中..." : "更新"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
