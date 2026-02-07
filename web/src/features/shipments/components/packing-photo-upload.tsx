"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Camera, Upload, X } from "lucide-react";
import { apiClient } from "@/lib/api/client";

interface PackingPhotoUploadProps {
  shipmentId: string;
  currentPhotoPath?: string | null;
  onUploadComplete?: () => void;
}

export function PackingPhotoUpload({
  shipmentId,
  currentPhotoPath,
  onUploadComplete,
}: PackingPhotoUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      setError("画像ファイルを選択してください");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError("ファイルサイズは10MB以下にしてください");
      return;
    }

    setError(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      setPreview(e.target?.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleUpload = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("photo", file);

      await apiClient(`/shipments/${shipmentId}/packing-photo`, {
        method: "POST",
        body: formData,
      });

      setPreview(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      onUploadComplete?.();
    } catch (err) {
      console.error("Upload failed:", err);
      setError("アップロードに失敗しました");
    } finally {
      setIsUploading(false);
    }
  };

  const handleClear = () => {
    setPreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Camera className="h-5 w-5" />
          梱包写真
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {currentPhotoPath && !preview && (
          <div className="text-sm text-green-600">
            梱包写真がアップロード済みです
          </div>
        )}

        {error && (
          <div className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md">
            {error}
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileSelect}
          className="hidden"
        />

        {preview ? (
          <div className="relative">
            <img
              src={preview}
              alt="プレビュー"
              className="max-h-48 rounded-lg object-cover"
            />
            <Button
              variant="ghost"
              size="sm"
              className="absolute top-2 right-2"
              onClick={handleClear}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <Button
            variant="outline"
            className="w-full h-24 border-dashed"
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="flex flex-col items-center gap-2">
              <Upload className="h-6 w-6" />
              <span>写真を選択</span>
            </div>
          </Button>
        )}

        {preview && (
          <Button
            onClick={handleUpload}
            disabled={isUploading}
            className="w-full"
          >
            {isUploading ? "アップロード中..." : "アップロード"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
