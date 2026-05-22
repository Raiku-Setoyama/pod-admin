"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Package, Upload } from "lucide-react";
import { apiClient, downloadFile } from "@/lib/api/client";
import type { TrackingFileImportResult } from "@/types/api";

interface TrackingImportProps {
  onImportComplete?: () => void;
}

export function TrackingImport({ onImportComplete }: TrackingImportProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [result, setResult] = useState<TrackingFileImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setSelectedFile(file);
    setResult(null);
    setError(null);
  };

  const handleImport = async () => {
    if (!selectedFile) {
      setError("ファイルを選択してください");
      return;
    }

    setIsImporting(true);
    setResult(null);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await apiClient<TrackingFileImportResult>(
        "/shipments/import",
        {
          method: "POST",
          body: formData,
        }
      );

      setResult(response);

      if (response.success_count > 0) {
        onImportComplete?.();
      }
    } catch (err) {
      console.error("Import failed:", err);
      setError("インポートに失敗しました");
    } finally {
      setIsImporting(false);
    }
  };

  const handleTemplateDownload = async () => {
    try {
      await downloadFile("/shipments/import-template", "import-template.csv");
    } catch {
      setError("テンプレートのダウンロードに失敗しました");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Package className="h-5 w-5" />
          伝票番号ファイルインポート
        </CardTitle>
        <CardDescription>
          CSV/XLSXファイルをアップロードして、伝票番号を一括登録します。
          ファイルには「注文番号」「伝票番号」列が必要です。「運送会社名」列はオプションです。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* テンプレートダウンロード */}
        <div>
          <button
            type="button"
            onClick={handleTemplateDownload}
            className="text-sm text-blue-600 hover:underline"
          >
            サンプルテンプレートをダウンロード
          </button>
        </div>

        {/* ファイル選択 */}
        <div className="space-y-2">
          <label className="text-sm font-medium">ファイル選択</label>
          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              accept=".csv,.xlsx"
              onChange={handleFileChange}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>
          {selectedFile && (
            <p className="text-sm text-gray-600">
              選択中: {selectedFile.name}
            </p>
          )}
        </div>

        {/* エラー表示 */}
        {error && (
          <div className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md">
            {error}
          </div>
        )}

        {/* インポート結果表示 */}
        {result && (
          <div className="space-y-2">
            <div className={`p-3 text-sm rounded-md border ${result.error_count > 0 ? "bg-yellow-50 border-yellow-200 text-yellow-800" : "bg-green-50 border-green-200 text-green-600"}`}>
              インポート完了: {result.success_count}件成功
              {result.error_count > 0 && `、${result.error_count}件失敗`}
            </div>

            {result.email_sent_count > 0 && (
              <div className="p-3 text-sm bg-blue-50 border border-blue-200 rounded-md text-blue-700">
                メール送信: {result.email_sent_count}件成功
              </div>
            )}

            {result.email_failed_count > 0 && (
              <div className="p-3 text-sm bg-orange-50 border border-orange-200 rounded-md text-orange-700">
                メール送信失敗: {result.email_failed_count}件（配送情報は更新済み）
              </div>
            )}

            {result.errors.length > 0 && (
              <div className="p-3 text-sm bg-red-50 border border-red-200 rounded-md space-y-1">
                <p className="font-medium text-red-700">エラー詳細:</p>
                {result.errors.map((error, index) => (
                  <div key={index} className="text-red-600">
                    行{error.row}: {error.order_number && <span>{error.order_number} - </span>}{error.message}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* インポートボタン */}
        <Button onClick={handleImport} disabled={isImporting || !selectedFile} className="w-full">
          <Upload className="h-4 w-4 mr-2" />
          {isImporting ? "インポート中..." : "インポート"}
        </Button>
      </CardContent>
    </Card>
  );
}
