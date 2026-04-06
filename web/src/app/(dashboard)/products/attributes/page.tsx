"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api/client";
import type {
  ProductType,
  ProductAttributeOption,
  ProductAttributeRequirement,
} from "@/types/api";

const productTypes: { value: ProductType; label: string }[] = [
  { value: "acrylic_keychain", label: "アクリルキーホルダー" },
  { value: "acrylic_stand", label: "アクリルスタンド" },
  { value: "sticker", label: "ステッカー" },
  { value: "tote_bag", label: "トートバッグ" },
  { value: "tshirt", label: "Tシャツ" },
];

const attributeNameLabels: Record<string, string> = {
  size: "サイズ",
  color: "カラー",
  position: "印刷位置",
};

export default function ProductAttributesPage() {
  const [selectedType, setSelectedType] = useState<ProductType>("tshirt");
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [newOption, setNewOption] = useState({
    attribute_name: "size" as string,
    attribute_value: "",
    display_order: 0,
  });
  const [error, setError] = useState<string | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  const {
    data: options,
    mutate: mutateOptions,
  } = useSWR<ProductAttributeOption[]>(
    `/product-attributes/${selectedType}/options`,
    apiClient
  );

  const {
    data: requirement,
    mutate: mutateRequirement,
  } = useSWR<ProductAttributeRequirement>(
    `/product-attributes/${selectedType}/requirements`,
    apiClient
  );

  const handleAddOption = useCallback(async () => {
    setError(null);
    try {
      await apiClient("/product-attributes/options", {
        method: "POST",
        body: {
          product_type: selectedType,
          ...newOption,
        },
      });
      setIsAddDialogOpen(false);
      setNewOption({ attribute_name: "size", attribute_value: "", display_order: 0 });
      mutateOptions();
    } catch (err: unknown) {
      if (err && typeof err === "object" && "message" in err) {
        setError((err as { message: string }).message);
      } else {
        setError("追加に失敗しました");
      }
    }
  }, [selectedType, newOption, mutateOptions]);

  const handleConfirmDelete = useCallback(async () => {
    if (!deleteTargetId) return;
    try {
      await apiClient(`/product-attributes/options/${deleteTargetId}`, {
        method: "DELETE",
      });
      mutateOptions();
      toast.success("属性オプションを削除しました");
    } catch {
      toast.error("削除に失敗しました");
    } finally {
      setDeleteTargetId(null);
    }
  }, [deleteTargetId, mutateOptions]);

  const handleToggleActive = useCallback(
    async (optionId: string, currentActive: boolean) => {
      try {
        await apiClient(`/product-attributes/options/${optionId}`, {
          method: "PATCH",
          body: { is_active: !currentActive },
        });
        mutateOptions();
      } catch {
        toast.error("更新に失敗しました");
      }
    },
    [mutateOptions]
  );

  const handleUpdateRequirement = useCallback(
    async (field: string, value: boolean) => {
      try {
        await apiClient(`/product-attributes/${selectedType}/requirements`, {
          method: "PATCH",
          body: { [field]: value },
        });
        mutateRequirement();
      } catch {
        toast.error("更新に失敗しました");
      }
    },
    [selectedType, mutateRequirement]
  );

  const groupedOptions = (options ?? []).reduce(
    (acc, opt) => {
      if (!acc[opt.attribute_name]) acc[opt.attribute_name] = [];
      acc[opt.attribute_name].push(opt);
      return acc;
    },
    {} as Record<string, ProductAttributeOption[]>
  );

  return (
    <PageContainer
      title="商品属性管理"
      description="商品種別ごとの属性オプション（サイズ・カラー・印刷位置）を管理します"
      actions={
        <Button onClick={() => setIsAddDialogOpen(true)}>
          <Plus className="h-4 w-4" />
          オプション追加
        </Button>
      }
    >
      <div className="space-y-6 p-6">
        {/* Product Type Selector */}
        <div className="flex items-center gap-4">
          <Label>商品種別:</Label>
          <Select
            value={selectedType}
            onValueChange={(v) => setSelectedType(v as ProductType)}
          >
            <SelectTrigger className="w-[240px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {productTypes.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Requirements Card */}
        {requirement && (
          <Card>
            <CardHeader>
              <CardTitle>必須設定</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-8">
                {(["required_size", "required_color", "required_position"] as const).map(
                  (field) => {
                    const label =
                      field === "required_size"
                        ? "サイズ必須"
                        : field === "required_color"
                          ? "カラー必須"
                          : "印刷位置必須";
                    return (
                      <div key={field} className="flex items-center gap-2">
                        <Switch
                          checked={requirement[field]}
                          onCheckedChange={(v) => handleUpdateRequirement(field, v)}
                        />
                        <Label>{label}</Label>
                      </div>
                    );
                  }
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Options by attribute_name */}
        {["size", "color", "position"].map((attrName) => {
          const items = groupedOptions[attrName] ?? [];
          return (
            <Card key={attrName}>
              <CardHeader>
                <CardTitle>{attributeNameLabels[attrName]}</CardTitle>
              </CardHeader>
              <CardContent>
                {items.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    オプションが登録されていません
                  </p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>値</TableHead>
                        <TableHead>表示順</TableHead>
                        <TableHead>ステータス</TableHead>
                        <TableHead className="w-[100px]">操作</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {items.map((opt) => (
                        <TableRow key={opt.id}>
                          <TableCell className="font-medium">
                            {opt.attribute_value}
                          </TableCell>
                          <TableCell>{opt.display_order}</TableCell>
                          <TableCell>
                            <Badge
                              variant={opt.is_active ? "default" : "secondary"}
                              className="cursor-pointer"
                              onClick={() =>
                                handleToggleActive(opt.id, opt.is_active)
                              }
                            >
                              {opt.is_active ? "有効" : "無効"}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setDeleteTargetId(opt.id)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Add Option Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>属性オプション追加</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {error && (
              <div className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <Label>属性種別</Label>
              <Select
                value={newOption.attribute_name}
                onValueChange={(v) =>
                  setNewOption({ ...newOption, attribute_name: v })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="size">サイズ</SelectItem>
                  <SelectItem value="color">カラー</SelectItem>
                  <SelectItem value="position">印刷位置</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>値</Label>
              <Input
                value={newOption.attribute_value}
                onChange={(e) =>
                  setNewOption({ ...newOption, attribute_value: e.target.value })
                }
                placeholder="例: XL, ブラック, 背面"
              />
            </div>
            <div className="space-y-2">
              <Label>表示順</Label>
              <Input
                type="number"
                min={0}
                value={newOption.display_order}
                onChange={(e) =>
                  setNewOption({
                    ...newOption,
                    display_order: parseInt(e.target.value) || 0,
                  })
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
              キャンセル
            </Button>
            <Button
              onClick={handleAddOption}
              disabled={!newOption.attribute_value.trim()}
            >
              追加
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <Dialog open={!!deleteTargetId} onOpenChange={(open) => !open && setDeleteTargetId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>属性オプションの削除</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            この属性オプションを削除しますか？この操作は元に戻せません。
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTargetId(null)}>
              キャンセル
            </Button>
            <Button variant="destructive" onClick={handleConfirmDelete}>
              削除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}
