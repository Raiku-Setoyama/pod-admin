"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FileUp, Package } from "lucide-react";
import { apiClient } from "@/lib/api/client";

interface TrackingImportProps {
  onImportComplete?: () => void;
}

const carriers = [
  { value: "yamato", label: "ヤマト運輸" },
  { value: "sagawa", label: "佐川急便" },
  { value: "japan_post", label: "日本郵便" },
  { value: "other", label: "その他" },
];

export function TrackingImport({ onImportComplete }: TrackingImportProps) {
  const [csvData, setCsvData] = useState("");
  const [carrier, setCarrier] = useState("yamato");
  const [isImporting, setIsImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ success: number; failed: number } | null>(null);

  const handleImport = async () => {
    if (!csvData.trim()) {
      setError("CSVデータを入力してください");
      return;
    }

    setIsImporting(true);
    setError(null);
    setResult(null);

    try {
      // Parse CSV: expected format is "shipment_id,tracking_number" per line
      const lines = csvData.trim().split("\n");
      const trackingData = lines
        .filter((line) => line.trim())
        .map((line) => {
          const [shipment_id, tracking_number] = line.split(",").map((s) => s.trim());
          return { shipment_id, tracking_number, carrier };
        })
        .filter((item) => item.shipment_id && item.tracking_number);

      if (trackingData.length === 0) {
        setError("有効なデータがありません。形式: 配送ID,伝票番号");
        return;
      }

      const response = await apiClient<unknown[]>("/shipments/import-tracking", {
        method: "POST",
        body: { items: trackingData },
      });

      setResult({
        success: response.length,
        failed: trackingData.length - response.length,
      });
      setCsvData("");
      onImportComplete?.();
    } catch (err) {
      console.error("Import failed:", err);
      setError("インポートに失敗しました");
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Package className="h-5 w-5" />
          伝票番号インポート
        </CardTitle>
        <CardDescription>
          CSVデータを貼り付けて、複数の配送に伝票番号を一括登録します。
          形式: 配送ID,伝票番号（1行1件）
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md">
            {error}
          </div>
        )}

        {result && (
          <div className="p-3 text-sm text-green-600 bg-green-50 border border-green-200 rounded-md">
            インポート完了: {result.success}件成功
            {result.failed > 0 && `、${result.failed}件失敗`}
          </div>
        )}

        <div className="space-y-2">
          <label className="text-sm font-medium">運送会社</label>
          <Select value={carrier} onValueChange={setCarrier}>
            <SelectTrigger>
              <SelectValue placeholder="運送会社を選択" />
            </SelectTrigger>
            <SelectContent>
              {carriers.map((c) => (
                <SelectItem key={c.value} value={c.value}>
                  {c.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">CSVデータ</label>
          <Textarea
            placeholder="例:&#10;abc12345,1234-5678-9012&#10;def67890,2345-6789-0123"
            value={csvData}
            onChange={(e) => setCsvData(e.target.value)}
            rows={6}
            className="font-mono text-sm"
          />
        </div>

        <Button onClick={handleImport} disabled={isImporting} className="w-full">
          <FileUp className="h-4 w-4 mr-2" />
          {isImporting ? "インポート中..." : "インポート"}
        </Button>
      </CardContent>
    </Card>
  );
}
