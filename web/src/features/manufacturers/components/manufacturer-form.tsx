"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
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
import type { Manufacturer, ProductType } from "@/types/api";

const productTypes: { value: ProductType; label: string }[] = [
  { value: "acrylic_keychain", label: "アクリルキーホルダー" },
  { value: "acrylic_stand", label: "アクリルスタンド" },
  { value: "sticker", label: "ステッカー" },
  { value: "mug", label: "マグカップ" },
  { value: "tshirt", label: "Tシャツ" },
];

const manufacturerSchema = z.object({
  name: z.string().min(1, "メーカー名を入力してください"),
  email: z.string().email("有効なメールアドレスを入力してください"),
  phone: z.string().optional(),
  supported_products: z.array(z.string()).min(1, "対応商品を1つ以上選択してください"),
  lead_time_days: z.number().min(1, "リードタイムは1日以上を入力してください"),
  daily_order_limit: z.number().min(1, "1日発注上限は1以上を入力してください"),
  sharing_method: z.enum(["DRIVE", "portal"]),
  is_active: z.boolean(),
  password: z.string().optional(),
});

type ManufacturerFormValues = z.infer<typeof manufacturerSchema>;

interface ManufacturerFormProps {
  manufacturer?: Manufacturer;
  onSuccess?: () => void;
  onCancel?: () => void;
}

export function ManufacturerForm({
  manufacturer,
  onSuccess,
  onCancel,
}: ManufacturerFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isEditing = !!manufacturer;

  const form = useForm<ManufacturerFormValues>({
    resolver: zodResolver(manufacturerSchema),
    defaultValues: {
      name: manufacturer?.name || "",
      email: manufacturer?.email || "",
      phone: manufacturer?.phone || "",
      supported_products: manufacturer?.supported_products || [],
      lead_time_days: manufacturer?.lead_time_days || 7,
      daily_order_limit: manufacturer?.daily_order_limit || 100,
      sharing_method: manufacturer?.sharing_method || "DRIVE",
      is_active: manufacturer?.is_active ?? true,
      password: "",
    },
  });

  const sharingMethod = form.watch("sharing_method");

  const onSubmit = async (data: ManufacturerFormValues) => {
    setIsSubmitting(true);
    setError(null);

    try {
      const payload = {
        ...data,
        unit_prices: data.supported_products.reduce((acc, product) => {
          acc[product] = manufacturer?.unit_prices?.[product] || 0;
          return acc;
        }, {} as Record<string, number>),
        password: data.password || undefined,
      };

      if (isEditing) {
        await apiClient(`/manufacturers/${manufacturer.id}`, { method: "PATCH", body: payload });
      } else {
        await apiClient("/manufacturers", { method: "POST", body: payload });
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

  const handleProductToggle = (product: string, checked: boolean) => {
    const current = form.getValues("supported_products");
    if (checked) {
      form.setValue("supported_products", [...current, product]);
    } else {
      form.setValue(
        "supported_products",
        current.filter((p) => p !== product)
      );
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
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>メーカー名</FormLabel>
                  <FormControl>
                    <Input placeholder="メーカー名を入力" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>メールアドレス</FormLabel>
                    <FormControl>
                      <Input type="email" placeholder="email@example.com" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>電話番号（任意）</FormLabel>
                    <FormControl>
                      <Input placeholder="03-1234-5678" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="is_active"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <FormLabel className="text-base">有効</FormLabel>
                    <FormDescription>
                      無効にすると発注先として選択できなくなります
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
            <CardTitle>対応商品</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {productTypes.map((product) => (
                <div
                  key={product.value}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <span>{product.label}</span>
                  <Switch
                    checked={form.watch("supported_products").includes(product.value)}
                    onCheckedChange={(checked) =>
                      handleProductToggle(product.value, checked)
                    }
                  />
                </div>
              ))}
            </div>
            {form.formState.errors.supported_products && (
              <p className="text-sm text-red-600 mt-2">
                {form.formState.errors.supported_products.message}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>発注設定</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
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
                        onChange={(e) => field.onChange(parseInt(e.target.value))}
                      />
                    </FormControl>
                    <FormDescription>
                      発注から納品までの日数
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="daily_order_limit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>1日発注上限</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={1}
                        {...field}
                        onChange={(e) => field.onChange(parseInt(e.target.value))}
                      />
                    </FormControl>
                    <FormDescription>
                      1日あたりの発注件数上限
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="sharing_method"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>共有方式</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="共有方式を選択" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="DRIVE">TOSYO DRIVE</SelectItem>
                      <SelectItem value="portal">メーカーポータル</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormDescription>
                    発注データの共有方法を選択
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {sharingMethod === "portal" && (
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      ポータルパスワード{isEditing && "（変更する場合のみ入力）"}
                    </FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        placeholder="ポータルログイン用パスワード"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}
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
