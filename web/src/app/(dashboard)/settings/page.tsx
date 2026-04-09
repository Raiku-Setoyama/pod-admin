"use client";

import { useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { Trash2, Plus } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageLoading } from "@/components/common/loading-spinner";
import { apiClient } from "@/lib/api/client";
import type {
  AppSettingListResponse,
  CompanyHolidayListResponse,
  CompanyHoliday,
} from "@/types/api";

export default function SettingsPage() {
  const [shippingDays, setShippingDays] = useState<string>("");
  const [shippingDaysLoaded, setShippingDaysLoaded] = useState(false);
  const [isSavingDays, setIsSavingDays] = useState(false);

  // 休日追加フォーム
  const [newHolidayDate, setNewHolidayDate] = useState("");
  const [newHolidayName, setNewHolidayName] = useState("");
  const [isAddingHoliday, setIsAddingHoliday] = useState(false);

  // 設定取得
  const { data: settingsData, mutate: mutateSettings } = useSWR<AppSettingListResponse>(
    "/settings",
    async (url: string) => {
      const data = await apiClient<AppSettingListResponse>(url);
      if (!shippingDaysLoaded) {
        const daysSetting = data.items.find((s) => s.key === "shipping_preparation_days");
        if (daysSetting) {
          setShippingDays(daysSetting.value);
        }
        setShippingDaysLoaded(true);
      }
      return data;
    }
  );

  // 休日一覧取得
  const {
    data: holidaysData,
    isLoading: isLoadingHolidays,
    mutate: mutateHolidays,
  } = useSWR<CompanyHolidayListResponse>("/company-holidays", apiClient);

  const handleSaveShippingDays = async () => {
    const days = parseInt(shippingDays, 10);
    if (isNaN(days) || days < 0 || days > 365) {
      toast.error("0〜365の整数で指定してください");
      return;
    }

    setIsSavingDays(true);
    try {
      await apiClient("/settings/shipping_preparation_days", {
        method: "PUT",
        body: { value: String(days) },
      });
      toast.success("発送準備日数を更新しました");
      mutateSettings();
    } catch {
      toast.error("更新に失敗しました");
    } finally {
      setIsSavingDays(false);
    }
  };

  const handleAddHoliday = async () => {
    if (!newHolidayDate || !newHolidayName.trim()) {
      toast.error("日付と名称を入力してください");
      return;
    }

    setIsAddingHoliday(true);
    try {
      await apiClient("/company-holidays", {
        method: "POST",
        body: { date: newHolidayDate, name: newHolidayName.trim() },
      });
      toast.success("休日を追加しました");
      setNewHolidayDate("");
      setNewHolidayName("");
      mutateHolidays();
    } catch {
      toast.error("追加に失敗しました（既に登録済みの可能性があります）");
    } finally {
      setIsAddingHoliday(false);
    }
  };

  const handleDeleteHoliday = async (holiday: CompanyHoliday) => {
    try {
      await apiClient(`/company-holidays/${holiday.id}`, {
        method: "DELETE",
      });
      toast.success(`${holiday.name} を削除しました`);
      mutateHolidays();
    } catch {
      toast.error("削除に失敗しました");
    }
  };

  const formatHolidayDate = (dateString: string) => {
    const date = new Date(dateString + "T00:00:00");
    return date.toLocaleDateString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      weekday: "short",
    });
  };

  return (
    <PageContainer title="設定" description="アプリケーション設定">
      <div className="max-w-2xl space-y-6">
        {/* 発送準備日数 */}
        <Card>
          <CardHeader>
            <CardTitle>配送設定</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="shipping-days">発送準備日数</Label>
              <p className="text-sm text-muted-foreground">
                納品完了後、発送までにかかる営業日数です。配送予定日の計算に使用されます。
              </p>
              <div className="flex items-center gap-3">
                <Input
                  id="shipping-days"
                  type="number"
                  min={0}
                  max={365}
                  value={shippingDays}
                  onChange={(e) => setShippingDays(e.target.value)}
                  className="w-24"
                />
                <span className="text-sm text-muted-foreground">営業日</span>
                <Button
                  onClick={handleSaveShippingDays}
                  disabled={isSavingDays}
                  size="sm"
                >
                  {isSavingDays ? "保存中..." : "保存"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 会社休日管理 */}
        <Card>
          <CardHeader>
            <CardTitle>会社休日</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              夏季休暇など、土日祝日以外の休業日を登録します。営業日計算に反映されます。
            </p>

            {/* 追加フォーム */}
            <div className="flex items-end gap-3">
              <div className="space-y-1">
                <Label htmlFor="holiday-date">日付</Label>
                <Input
                  id="holiday-date"
                  type="date"
                  value={newHolidayDate}
                  onChange={(e) => setNewHolidayDate(e.target.value)}
                  className="w-44"
                />
              </div>
              <div className="space-y-1 flex-1">
                <Label htmlFor="holiday-name">名称</Label>
                <Input
                  id="holiday-name"
                  placeholder="例: 夏季休暇"
                  value={newHolidayName}
                  onChange={(e) => setNewHolidayName(e.target.value)}
                />
              </div>
              <Button
                onClick={handleAddHoliday}
                disabled={isAddingHoliday}
                size="sm"
              >
                <Plus className="h-4 w-4 mr-1" />
                追加
              </Button>
            </div>

            {/* 休日一覧テーブル */}
            {isLoadingHolidays ? (
              <PageLoading />
            ) : (
              <div className="rounded-lg border border-border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>日付</TableHead>
                      <TableHead>名称</TableHead>
                      <TableHead className="w-16" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(!holidaysData?.items || holidaysData.items.length === 0) ? (
                      <TableRow>
                        <TableCell colSpan={3} className="h-16 text-center text-muted-foreground">
                          登録された休日はありません
                        </TableCell>
                      </TableRow>
                    ) : (
                      holidaysData.items.map((holiday) => (
                        <TableRow key={holiday.id}>
                          <TableCell>{formatHolidayDate(holiday.date)}</TableCell>
                          <TableCell>{holiday.name}</TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteHoliday(holiday)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}
