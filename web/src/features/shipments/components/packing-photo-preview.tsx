"use client";

import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogClose,
  DialogTitle,
} from "@/components/ui/dialog";
import { Camera, Upload, X, Loader2 } from "lucide-react";
import { getApiBaseUrl, apiClient } from "@/lib/api/client";

interface PackingPhotoPreviewProps {
  shipmentId: string;
  packingPhotoPath?: string | null;
  onUploadComplete?: () => void;
}

export function PackingPhotoPreview({
  shipmentId,
  packingPhotoPath,
  onUploadComplete,
}: PackingPhotoPreviewProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadPreview, setUploadPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const hasPhoto = !!packingPhotoPath;
  const photoUrl = hasPhoto
    ? `${getApiBaseUrl()}/shipments/${shipmentId}/packing-photo`
    : null;

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
      setUploadPreview(e.target?.result as string);
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

      setUploadPreview(null);
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
    setUploadPreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleImageLoad = () => {
    setIsLoading(false);
  };

  const handleImageError = () => {
    setIsLoading(false);
    setError("画像の読み込みに失敗しました");
  };

  const handleThumbnailClick = () => {
    if (hasPhoto && !error) {
      setIsModalOpen(true);
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

        {uploadPreview ? (
          <div className="relative">
            <img
              src={uploadPreview}
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
        ) : hasPhoto && photoUrl ? (
          <div className="relative">
            {isLoading && (
              <div
                data-testid="photo-loading"
                className="absolute inset-0 flex items-center justify-center bg-gray-100 rounded-lg"
              >
                <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              </div>
            )}
            <img
              src={photoUrl}
              alt="梱包写真"
              className={`max-h-48 rounded-lg object-cover cursor-pointer hover:opacity-90 transition-opacity ${
                isLoading ? "invisible" : "visible"
              }`}
              onLoad={handleImageLoad}
              onError={handleImageError}
              onClick={handleThumbnailClick}
            />
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

        {uploadPreview && (
          <Button
            onClick={handleUpload}
            disabled={isUploading}
            className="w-full"
          >
            {isUploading ? "アップロード中..." : "アップロード"}
          </Button>
        )}

        {hasPhoto && !uploadPreview && (
          <Button
            variant="outline"
            className="w-full"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className="h-4 w-4 mr-2" />
            写真を変更
          </Button>
        )}

        {/* 拡大表示モーダル */}
        <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
          <DialogContent className="max-w-4xl p-0 overflow-hidden" showCloseButton={false} aria-describedby={undefined}>
            <DialogTitle className="sr-only">梱包写真の拡大表示</DialogTitle>
            <div className="relative">
              <img
                src={photoUrl || ""}
                alt="梱包写真（拡大）"
                className="w-full h-auto"
              />
              <DialogClose asChild>
                <Button
                  variant="secondary"
                  size="sm"
                  className="absolute top-4 right-4"
                  aria-label="閉じる"
                >
                  <X className="h-4 w-4 mr-1" />
                  閉じる
                </Button>
              </DialogClose>
            </div>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}
