"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Download, FileText } from "lucide-react";
import { apiClient } from "@/lib/api/client";

interface ShipmentDocumentsProps {
  shipmentId: string;
}

type DocumentFormat = "shipping_label" | "packing_list";
type Carrier = "yamato" | "sagawa" | "japan_post";

const formatOptions: { value: DocumentFormat; label: string }[] = [
  { value: "shipping_label", label: "配送ラベル CSV" },
  { value: "packing_list", label: "同梱商品リスト CSV" },
];

const carrierOptions: { value: Carrier; label: string }[] = [
  { value: "yamato", label: "ヤマト運輸" },
  { value: "sagawa", label: "佐川急便" },
  { value: "japan_post", label: "日本郵便" },
];

export function ShipmentDocuments({ shipmentId }: ShipmentDocumentsProps) {
  const [format, setFormat] = useState<DocumentFormat>("shipping_label");
  const [carrier, setCarrier] = useState<Carrier>("yamato");
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const data = await apiClient<Blob>(
        `/shipments/${shipmentId}/documents?format=${format}&carrier=${carrier}`
      );

      const filename =
        format === "shipping_label"
          ? `配送ラベル_${shipmentId.slice(0, 8)}.csv`
          : `同梱リスト_${shipmentId.slice(0, 8)}.csv`;

      const blob = new Blob([data], { type: "text/csv" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Download failed:", error);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <FileText className="h-5 w-5" />
        <span className="font-medium">配送資料ダウンロード</span>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Select value={format} onValueChange={(value) => setFormat(value as DocumentFormat)}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="資料形式を選択" />
          </SelectTrigger>
          <SelectContent>
            {formatOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {format === "shipping_label" && (
          <Select value={carrier} onValueChange={(value) => setCarrier(value as Carrier)}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="運送会社" />
            </SelectTrigger>
            <SelectContent>
              {carrierOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <Button onClick={handleDownload} disabled={isDownloading} size="sm">
          <Download className="mr-2 h-4 w-4" />
          {isDownloading ? "ダウンロード中..." : "ダウンロード"}
        </Button>
      </div>
    </div>
  );
}
