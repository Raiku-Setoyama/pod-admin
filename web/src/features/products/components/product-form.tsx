"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { apiClient } from "@/lib/api/client";
import type { Product, ProductType, ManufacturerListResponse, ProductAttributeSpec } from "@/types/api";

const productTypes: { value: ProductType; label: string }[] = [
  { value: "acrylic_keychain", label: "アクリルキーホルダー" },
  { value: "acrylic_stand", label: "アクリルスタンド" },
  { value: "sticker", label: "ステッカー" },
  { value: "tote_bag", label: "トートバッグ" },
  { value: "tshirt", label: "Tシャツ" },
];

const productSchema = z.object({
  product_type: z.enum([
    "acrylic_keychain",
    "acrylic_stand",
    "sticker",
    "tote_bag",
    "tshirt",
  ]),
  size: z.string().optional(),
  position: z.string().optional(),
  color: z.string().optional(),
  manufacturer_id: z.string().optional(),
  cost: z.number().min(0, "原価は0以上を入力してください"),
  lead_time_days: z.number().min(1, "リードタイムは1日以上を入力してください"),
  order_limit: z.number().optional(),
  is_active: z.boolean(),
});

type ProductFormValues = z.infer<typeof productSchema>;

interface ProductFormProps {
  product?: Product;
  onSuccess?: () => void;
  onCancel?: () => void;
}

const fetcher = (url: string) => apiClient<ManufacturerListResponse>(url);
const attributeFetcher = (url: string) => apiClient<ProductAttributeSpec>(url);

export function ProductForm({
  product,
  onSuccess,
  onCancel,
}: ProductFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isEditing = !!product;

  const { data: manufacturersData } = useSWR<ManufacturerListResponse>(
    "/manufacturers?limit=100",
    fetcher
  );

  const manufacturers = manufacturersData?.items || [];

  const form = useForm<ProductFormValues>({
    resolver: zodResolver(productSchema),
    defaultValues: {
      product_type: product?.product_type || "acrylic_keychain",
      size: product?.size || "",
      position: product?.position || "",
      color: product?.color || "",
      manufacturer_id: product?.manufacturer_id || "",
      cost: product?.cost || 0,
      lead_time_days: product?.lead_time_days || 7,
      order_limit: product?.order_limit || undefined,
      is_active: product?.is_active ?? true,
    },
  });

  const selectedProductType = form.watch("product_type");

  const { data: attributeSpec } = useSWR<ProductAttributeSpec>(
    selectedProductType ? `/products/attributes/${selectedProductType}` : null,
    attributeFetcher
  );

  // Reset attribute fields when product_type changes (new product only)
  useEffect(() => {
    if (!isEditing) {
      form.setValue("size", "");
      form.setValue("color", "");
      form.setValue("position", "");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProductType]);

  const onSubmit = async (data: ProductFormValues) => {
    setIsSubmitting(true);
    setError(null);

    try {
      const payload = {
        ...data,
        manufacturer_id: data.manufacturer_id || null,
        order_limit: data.order_limit || null,
      };

      if (isEditing) {
        await apiClient(`/products/${product.id}`, { method: "PATCH", body: payload });
      } else {
        await apiClient("/products", { method: "POST", body: payload });
      }

      onSuccess?.();
    } catch (err: unknown) {
      if (err && typeof err === "object" && "response" in err) {
        const axiosError = err as { response?: { data?: { error?: { message?: string } } } };
        setError(axiosError.response?.data?.error?.message || "保存に失敗しました");
      } else {
        setError("保存に失敗しました");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        {error && (
          <div className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md">
            {error}
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle>基本情報</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="product_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>商品種別</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="商品種別を選択" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {productTypes.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-3 gap-4">
              {attributeSpec && attributeSpec.sizes.length > 0 && (
                <FormField
                  control={form.control}
                  name="size"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        サイズ{attributeSpec.required_size ? "（必須）" : "（任意）"}
                      </FormLabel>
                      <Select onValueChange={field.onChange} value={field.value || ""}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="サイズを選択" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {attributeSpec.sizes.map((s) => (
                            <SelectItem key={s} value={s}>{s}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {attributeSpec && attributeSpec.colors.length > 0 && (
                <FormField
                  control={form.control}
                  name="color"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        カラー{attributeSpec.required_color ? "（必須）" : "（任意）"}
                      </FormLabel>
                      <Select onValueChange={field.onChange} value={field.value || ""}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="カラーを選択" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {attributeSpec.colors.map((c) => (
                            <SelectItem key={c} value={c}>{c}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {attributeSpec && attributeSpec.positions.length > 0 && (
                <FormField
                  control={form.control}
                  name="position"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        印刷位置{attributeSpec.required_position ? "（必須）" : "（任意）"}
                      </FormLabel>
                      <Select onValueChange={field.onChange} value={field.value || ""}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="印刷位置を選択" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {attributeSpec.positions.map((p) => (
                            <SelectItem key={p} value={p}>{p}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
            </div>

            <FormField
              control={form.control}
              name="is_active"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <FormLabel className="text-base">有効</FormLabel>
                    <FormDescription>
                      無効にすると受注時に選択できなくなります
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>製造情報</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="manufacturer_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>製造メーカー（任意）</FormLabel>
                  <Select
                    onValueChange={(value) => field.onChange(value === "__none__" ? "" : value)}
                    defaultValue={field.value || "__none__"}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="メーカーを選択" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="__none__">未設定</SelectItem>
                      {manufacturers.map((manufacturer) => (
                        <SelectItem key={manufacturer.id} value={manufacturer.id}>
                          {manufacturer.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormDescription>
                    発注時に自動でこのメーカーが選択されます
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="cost"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>原価（円）</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={0}
                        {...field}
                        onChange={(e) => field.onChange(parseInt(e.target.value) || 0)}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="lead_time_days"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>リードタイム（日）</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={1}
                        {...field}
                        onChange={(e) => field.onChange(parseInt(e.target.value) || 1)}
                      />
                    </FormControl>
                    <FormDescription>
                      発注から納品までの日数
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="order_limit"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>発注上限（任意）</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      min={1}
                      placeholder="上限なしの場合は空欄"
                      value={field.value || ""}
                      onChange={(e) =>
                        field.onChange(e.target.value ? parseInt(e.target.value) : undefined)
                      }
                    />
                  </FormControl>
                  <FormDescription>
                    1回の発注で注文できる最大数
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        <div className="flex justify-end gap-3">
          {onCancel && (
            <Button type="button" variant="outline" onClick={onCancel}>
              キャンセル
            </Button>
          )}
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "保存中..." : isEditing ? "更新" : "登録"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
