"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Loader2, Save, Building2, CreditCard, User } from "lucide-react";
import { toast } from "sonner";
import {
  useManufacturerProfile,
  updateManufacturerProfile,
} from "@/features/manufacturer-portal/hooks/use-manufacturer-profile";
import type { ManufacturerProfileUpdate } from "@/types/api";

export default function ManufacturerSettingsPage() {
  const { profile, isLoading, mutate } = useManufacturerProfile();
  const [isSaving, setIsSaving] = useState(false);

  // Form state
  const [formData, setFormData] = useState<ManufacturerProfileUpdate>({});

  // Initialize form data when profile loads
  useEffect(() => {
    if (profile) {
      setFormData({
        phone: profile.phone,
        postal_code: profile.postal_code,
        address: profile.address,
        bank_name: profile.bank_name,
        bank_branch: profile.bank_branch,
        bank_account_type: profile.bank_account_type,
        bank_account_number: profile.bank_account_number,
        bank_account_holder: profile.bank_account_holder,
        representative_name: profile.representative_name,
        invoice_notes: profile.invoice_notes,
      });
    }
  }, [profile]);

  const handleChange = (field: keyof ManufacturerProfileUpdate, value: string | null) => {
    setFormData((prev) => ({ ...prev, [field]: value || null }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);

    try {
      await updateManufacturerProfile(formData);
      await mutate();
      toast.success("プロフィールを更新しました");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "プロフィールの更新に失敗しました"
      );
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">アカウント設定</h2>
        <p className="text-muted-foreground">
          請求書に記載される情報を設定します
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* 基本情報 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              基本情報
            </CardTitle>
            <CardDescription>
              会社名・メールアドレスは管理者にお問い合わせください
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>会社名</Label>
                <Input value={profile?.name || ""} disabled />
              </div>
              <div className="space-y-2">
                <Label>メールアドレス</Label>
                <Input value={profile?.email || ""} disabled />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="phone">電話番号</Label>
                <Input
                  id="phone"
                  value={formData.phone || ""}
                  onChange={(e) => handleChange("phone", e.target.value)}
                  placeholder="03-1234-5678"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="representative_name">代表者名</Label>
                <Input
                  id="representative_name"
                  value={formData.representative_name || ""}
                  onChange={(e) => handleChange("representative_name", e.target.value)}
                  placeholder="代表取締役 山田太郎"
                />
              </div>
            </div>
            <Separator />
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="postal_code">郵便番号</Label>
                <Input
                  id="postal_code"
                  value={formData.postal_code || ""}
                  onChange={(e) => handleChange("postal_code", e.target.value)}
                  placeholder="123-4567"
                />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="address">住所</Label>
                <Input
                  id="address"
                  value={formData.address || ""}
                  onChange={(e) => handleChange("address", e.target.value)}
                  placeholder="東京都渋谷区..."
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 銀行口座情報 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5" />
              銀行口座情報
            </CardTitle>
            <CardDescription>
              請求書に記載される振込先口座情報
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="bank_name">銀行名</Label>
                <Input
                  id="bank_name"
                  value={formData.bank_name || ""}
                  onChange={(e) => handleChange("bank_name", e.target.value)}
                  placeholder="三菱UFJ銀行"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bank_branch">支店名</Label>
                <Input
                  id="bank_branch"
                  value={formData.bank_branch || ""}
                  onChange={(e) => handleChange("bank_branch", e.target.value)}
                  placeholder="渋谷支店"
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="bank_account_type">口座種別</Label>
                <Select
                  value={formData.bank_account_type || ""}
                  onValueChange={(value) =>
                    handleChange("bank_account_type", value as "普通" | "当座")
                  }
                >
                  <SelectTrigger id="bank_account_type">
                    <SelectValue placeholder="選択してください" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="普通">普通</SelectItem>
                    <SelectItem value="当座">当座</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="bank_account_number">口座番号</Label>
                <Input
                  id="bank_account_number"
                  value={formData.bank_account_number || ""}
                  onChange={(e) => handleChange("bank_account_number", e.target.value)}
                  placeholder="1234567"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bank_account_holder">口座名義</Label>
                <Input
                  id="bank_account_holder"
                  value={formData.bank_account_holder || ""}
                  onChange={(e) => handleChange("bank_account_holder", e.target.value)}
                  placeholder="カ）サンプル"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 請求書備考 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              請求書備考
            </CardTitle>
            <CardDescription>
              請求書に記載する備考（支払条件など）
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              id="invoice_notes"
              value={formData.invoice_notes || ""}
              onChange={(e) => handleChange("invoice_notes", e.target.value)}
              placeholder="お支払いは請求月の翌月末日までにお願いいたします。"
              rows={3}
            />
          </CardContent>
        </Card>

        {/* 保存ボタン */}
        <div className="flex justify-end">
          <Button type="submit" disabled={isSaving}>
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            保存する
          </Button>
        </div>
      </form>
    </div>
  );
}
