"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api/client";
import type { OrderSource } from "@/types/api";

interface OrderSourceFormDialogProps {
  open: boolean;
  orderSource?: OrderSource;
  onClose: () => void;
  onSuccess: () => void;
}

interface FormData {
  code: string;
  name: string;
  api_key: string;
  phone: string;
  postal_code: string;
  address_prefecture: string;
  address_city: string;
  address_building: string;
}

interface FormErrors {
  code?: string;
  name?: string;
  api_key?: string;
  phone?: string;
  postal_code?: string;
  address_prefecture?: string;
  address_city?: string;
}

const initialFormData: FormData = {
  code: "",
  name: "",
  api_key: "",
  phone: "",
  postal_code: "",
  address_prefecture: "",
  address_city: "",
  address_building: "",
};

export function OrderSourceFormDialog({
  open,
  orderSource,
  onClose,
  onSuccess,
}: OrderSourceFormDialogProps) {
  const isEdit = !!orderSource;
  const [formData, setFormData] = useState<FormData>(initialFormData);
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      if (orderSource) {
        setFormData({
          code: orderSource.code,
          name: orderSource.name,
          api_key: orderSource.api_key,
          phone: orderSource.phone,
          postal_code: orderSource.postal_code,
          address_prefecture: orderSource.address_prefecture,
          address_city: orderSource.address_city,
          address_building: orderSource.address_building ?? "",
        });
      } else {
        setFormData(initialFormData);
      }
      setErrors({});
    }
  }, [open, orderSource]);

  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.code.trim()) newErrors.code = "必須項目です";
    if (!formData.name.trim()) newErrors.name = "必須項目です";
    if (!formData.api_key.trim()) newErrors.api_key = "必須項目です";
    if (!formData.phone.trim()) newErrors.phone = "必須項目です";
    if (!formData.postal_code.trim()) newErrors.postal_code = "必須項目です";
    if (!formData.address_prefecture.trim())
      newErrors.address_prefecture = "必須項目です";
    if (!formData.address_city.trim()) newErrors.address_city = "必須項目です";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    setIsSubmitting(true);
    try {
      if (isEdit) {
        await apiClient(`/order-sources/${orderSource!.id}`, {
          method: "PATCH",
          body: {
            code: formData.code,
            name: formData.name,
            api_key: formData.api_key,
            phone: formData.phone,
            postal_code: formData.postal_code,
            address_prefecture: formData.address_prefecture,
            address_city: formData.address_city,
            address_building: formData.address_building || null,
          },
        });
      } else {
        await apiClient("/order-sources", {
          method: "POST",
          body: {
            code: formData.code,
            name: formData.name,
            api_key: formData.api_key,
            phone: formData.phone,
            postal_code: formData.postal_code,
            address_prefecture: formData.address_prefecture,
            address_city: formData.address_city,
            address_building: formData.address_building || null,
          },
        });
      }
      onSuccess();
    } catch {
      // Error handling can be added here
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field: keyof FormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "受注元編集" : "受注元登録"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="os-code">受注元コード</Label>
              <Input
                id="os-code"
                value={formData.code}
                onChange={(e) => handleChange("code", e.target.value)}
              />
              {errors.code && (
                <p className="text-sm text-red-500">{errors.code}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="os-name">受注元名</Label>
              <Input
                id="os-name"
                value={formData.name}
                onChange={(e) => handleChange("name", e.target.value)}
              />
              {errors.name && (
                <p className="text-sm text-red-500">{errors.name}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="os-api-key">APIキー</Label>
              <Input
                id="os-api-key"
                value={formData.api_key}
                onChange={(e) => handleChange("api_key", e.target.value)}
              />
              {errors.api_key && (
                <p className="text-sm text-red-500">{errors.api_key}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="os-phone">電話番号</Label>
              <Input
                id="os-phone"
                value={formData.phone}
                onChange={(e) => handleChange("phone", e.target.value)}
              />
              {errors.phone && (
                <p className="text-sm text-red-500">{errors.phone}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="os-postal-code">郵便番号</Label>
              <Input
                id="os-postal-code"
                value={formData.postal_code}
                onChange={(e) => handleChange("postal_code", e.target.value)}
              />
              {errors.postal_code && (
                <p className="text-sm text-red-500">{errors.postal_code}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="os-prefecture">都道府県</Label>
              <Input
                id="os-prefecture"
                value={formData.address_prefecture}
                onChange={(e) =>
                  handleChange("address_prefecture", e.target.value)
                }
              />
              {errors.address_prefecture && (
                <p className="text-sm text-red-500">
                  {errors.address_prefecture}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="os-city">市区町村</Label>
              <Input
                id="os-city"
                value={formData.address_city}
                onChange={(e) => handleChange("address_city", e.target.value)}
              />
              {errors.address_city && (
                <p className="text-sm text-red-500">{errors.address_city}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="os-building">建物名</Label>
              <Input
                id="os-building"
                value={formData.address_building}
                onChange={(e) =>
                  handleChange("address_building", e.target.value)
                }
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              キャンセル
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "保存中..." : "保存"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
