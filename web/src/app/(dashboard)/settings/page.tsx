"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { Trash2, Plus } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageLoading } from "@/components/common/loading-spinner";
import { EmailListInput } from "@/components/common/email-list-input";
import { apiClient } from "@/lib/api/client";
import type {
  AppSettingListResponse,
  CompanyHolidayListResponse,
  CompanyHoliday,
} from "@/types/api";

const NOTIFICATION_ENABLED_KEY = "external_order_notification_enabled";
const NOTIFICATION_RECIPIENTS_KEY = "external_order_notification_recipients";
const DIGEST_ENABLED_KEY = "manufacturer_daily_digest_enabled";
const DIGEST_SEND_TIME_KEY = "manufacturer_daily_digest_send_time";
const TIME_REGEX = /^([01]\d|2[0-3]):[0-5]\d$/;
const ORDER_DEADLINE_TIME_KEY = "order_deadline_time";
// "HH:MM"（00:00〜23:59）。空文字は無効化として許可する。
const DEADLINE_TIME_REGEX = /^([01]\d|2[0-3]):([0-5]\d)$/;

function parseRecipients(value: string | undefined): string[] {
  if (!value) return [];
  return value
    .split(",")
    .map((addr) => addr.trim())
    .filter(Boolean);
}

export default function SettingsPage() {
  const [shippingDays, setShippingDays] = useState<string>("");
  const [shippingDaysInitialized, setShippingDaysInitialized] = useState(false);
  const [isSavingDays, setIsSavingDays] = useState(false);

  // 注文〆切時間（HH:MM・JST、空欄で無効）
  const [deadlineTime, setDeadlineTime] = useState<string>("");
  const [deadlineInitialized, setDeadlineInitialized] = useState(false);
  const [isSavingDeadline, setIsSavingDeadline] = useState(false);
  const [deadlineError, setDeadlineError] = useState<string | null>(null);

  // 外部注文の通知
  const [notificationEnabled, setNotificationEnabled] = useState(false);
  const [recipients, setRecipients] = useState<string[]>([]);
  const [notificationInitialized, setNotificationInitialized] = useState(false);
  const [isSavingNotification, setIsSavingNotification] = useState(false);
  const [notificationError, setNotificationError] = useState<string | null>(null);

  // メーカー日次発注通知（全社共通）
  const [digestEnabled, setDigestEnabled] = useState(false);
  const [digestSendTime, setDigestSendTime] = useState("09:00");
  const [digestInitialized, setDigestInitialized] = useState(false);
  const [isSavingDigest, setIsSavingDigest] = useState(false);

  // 休日追加フォーム
  const [newHolidayDate, setNewHolidayDate] = useState("");
  const [newHolidayName, setNewHolidayName] = useState("");
  const [isAddingHoliday, setIsAddingHoliday] = useState(false);

  // 設定取得
  const { data: settingsData, mutate: mutateSettings } = useSWR<AppSettingListResponse>(
    "/settings",
    apiClient,
  );

  // 初回データ取得時にフォームへ反映
  useEffect(() => {
    if (settingsData && !shippingDaysInitialized) {
      const daysSetting = settingsData.items.find((s) => s.key === "shipping_preparation_days");
      if (daysSetting) {
        setShippingDays(daysSetting.value);
      }
      setShippingDaysInitialized(true);
    }
  }, [settingsData, shippingDaysInitialized]);

  // 注文〆切時間の初回反映
  useEffect(() => {
    if (settingsData && !deadlineInitialized) {
      const deadlineSetting = settingsData.items.find(
        (s) => s.key === ORDER_DEADLINE_TIME_KEY,
      );
      setDeadlineTime(deadlineSetting?.value ?? "");
      setDeadlineInitialized(true);
    }
  }, [settingsData, deadlineInitialized]);

  // 通知設定の初回反映
  useEffect(() => {
    if (settingsData && !notificationInitialized) {
      const enabledSetting = settingsData.items.find((s) => s.key === NOTIFICATION_ENABLED_KEY);
      setNotificationEnabled(enabledSetting?.value === "true");
      const recipientsSetting = settingsData.items.find(
        (s) => s.key === NOTIFICATION_RECIPIENTS_KEY,
      );
      setRecipients(parseRecipients(recipientsSetting?.value));
      setNotificationInitialized(true);
    }
  }, [settingsData, notificationInitialized]);

  // メーカー日次発注通知の初回反映
  useEffect(() => {
    if (settingsData && !digestInitialized) {
      const enabledSetting = settingsData.items.find((s) => s.key === DIGEST_ENABLED_KEY);
      setDigestEnabled(enabledSetting?.value === "true");
      const sendTimeSetting = settingsData.items.find((s) => s.key === DIGEST_SEND_TIME_KEY);
      if (sendTimeSetting?.value) {
        setDigestSendTime(sendTimeSetting.value);
      }
      setDigestInitialized(true);
    }
  }, [settingsData, digestInitialized]);

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

  const handleSaveDeadline = async () => {
    const value = deadlineTime.trim();
    // 空欄は無効化として許可。それ以外は HH:MM 形式を要求する。
    if (value !== "" && !DEADLINE_TIME_REGEX.test(value)) {
      setDeadlineError("注文〆切時間は HH:MM 形式（00:00〜23:59）で指定してください");
      return;
    }

    setIsSavingDeadline(true);
    setDeadlineError(null);
    try {
      await apiClient(`/settings/${ORDER_DEADLINE_TIME_KEY}`, {
        method: "PUT",
        body: { value },
      });
      toast.success(
        value === "" ? "注文〆切時間を無効にしました" : "注文〆切時間を更新しました",
      );
      mutateSettings();
    } catch (err) {
      const message = err instanceof Error ? err.message : "更新に失敗しました";
      setDeadlineError(message);
      toast.error(message);
    } finally {
      setIsSavingDeadline(false);
    }
  };

  const handleSaveNotification = async () => {
    setIsSavingNotification(true);
    setNotificationError(null);
    try {
      await apiClient(`/settings/${NOTIFICATION_ENABLED_KEY}`, {
        method: "PUT",
        body: { value: notificationEnabled ? "true" : "false" },
      });
      await apiClient(`/settings/${NOTIFICATION_RECIPIENTS_KEY}`, {
        method: "PUT",
        body: { value: recipients.join(",") },
      });
      toast.success("外部注文の通知設定を更新しました");
      mutateSettings();
    } catch (err) {
      const message = err instanceof Error ? err.message : "更新に失敗しました";
      setNotificationError(message);
      toast.error(message);
    } finally {
      setIsSavingNotification(false);
    }
  };

  const handleSaveDigest = async () => {
    if (!TIME_REGEX.test(digestSendTime)) {
      toast.error("送信時刻は HH:MM（24時間表記）で指定してください");
      return;
    }
    setIsSavingDigest(true);
    try {
      await apiClient(`/settings/${DIGEST_ENABLED_KEY}`, {
        method: "PUT",
        body: { value: digestEnabled ? "true" : "false" },
      });
      await apiClient(`/settings/${DIGEST_SEND_TIME_KEY}`, {
        method: "PUT",
        body: { value: digestSendTime },
      });
      toast.success("メーカー日次発注通知の設定を更新しました");
      mutateSettings();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "更新に失敗しました");
    } finally {
      setIsSavingDigest(false);
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

            <div className="space-y-2">
              <Label htmlFor="deadline-time">注文〆切時間</Label>
              <p className="text-sm text-muted-foreground">
                この時刻（JST）以降に着信した注文は、翌営業日を起算日として納品予定日・配送予定日を計算します。空欄にすると無効になり、すべて当日起算になります。
              </p>
              <div className="flex items-center gap-3">
                <Input
                  id="deadline-time"
                  type="time"
                  value={deadlineTime}
                  onChange={(e) => setDeadlineTime(e.target.value)}
                  className="w-32"
                />
                <Button
                  onClick={handleSaveDeadline}
                  disabled={isSavingDeadline}
                  size="sm"
                >
                  {isSavingDeadline ? "保存中..." : "保存"}
                </Button>
              </div>
              {deadlineError && (
                <p className="text-sm text-destructive" role="alert">
                  {deadlineError}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* 外部注文の通知 */}
        <Card>
          <CardHeader>
            <CardTitle>外部注文の通知</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              外部販売サイトから注文を受け付けた際に、指定したメールアドレスへ通知メールを送信します。
            </p>

            <div className="flex items-center gap-3">
              <Switch
                id="notification-enabled"
                checked={notificationEnabled}
                onCheckedChange={setNotificationEnabled}
              />
              <Label htmlFor="notification-enabled">通知を有効にする</Label>
            </div>

            <div className="space-y-2">
              <EmailListInput
                id="recipient-email"
                label="通知先メールアドレス"
                description="複数登録できます。入力して「追加」を押すか Enter で登録してください。"
                emails={recipients}
                onChange={setRecipients}
                placeholder="例: staff@example.com"
                emptyText="通知先が登録されていません。"
              />

              {notificationEnabled && recipients.length === 0 && (
                <p className="text-sm text-amber-600">
                  宛先が未登録のため、現在は通知が送信されません。
                </p>
              )}
              {notificationError && (
                <p className="text-sm text-destructive" role="alert">
                  {notificationError}
                </p>
              )}
            </div>

            <Button
              onClick={handleSaveNotification}
              disabled={isSavingNotification}
              size="sm"
            >
              {isSavingNotification ? "保存中..." : "保存"}
            </Button>
          </CardContent>
        </Card>

        {/* メーカー日次発注通知（全社共通） */}
        <Card>
          <CardHeader>
            <CardTitle>メーカー日次発注通知</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              毎日決まった時刻に、新規の発注済み明細があるメーカーへ発注通知メールを送信します。
              宛先や有効/無効はメーカーごとに各メーカーの編集画面で設定します。
            </p>

            <div className="flex items-center gap-3">
              <Switch
                id="digest-enabled"
                checked={digestEnabled}
                onCheckedChange={setDigestEnabled}
              />
              <Label htmlFor="digest-enabled">日次通知を有効にする（全体）</Label>
            </div>

            <div className="space-y-2">
              <Label htmlFor="digest-send-time">送信時刻（JST・全社共通）</Label>
              <p className="text-sm text-muted-foreground">
                この時刻を過ぎた最初のタイミングで、1 日 1 回送信されます。変更は翌日以降の送信に反映されます。
              </p>
              <Input
                id="digest-send-time"
                type="time"
                value={digestSendTime}
                onChange={(e) => setDigestSendTime(e.target.value)}
                className="w-32"
              />
            </div>

            <Button onClick={handleSaveDigest} disabled={isSavingDigest} size="sm">
              {isSavingDigest ? "保存中..." : "保存"}
            </Button>
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
