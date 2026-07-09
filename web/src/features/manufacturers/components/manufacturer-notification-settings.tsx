"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { EmailListInput } from "@/components/common/email-list-input";
import { apiClient } from "@/lib/api/client";
import type { ManufacturerNotificationSettings } from "@/types/api";

interface ManufacturerNotificationSettingsCardProps {
  manufacturerId: string;
  manufacturerEmail: string;
}

/** メーカー別の日次発注通知設定（ON/OFF・To/CC）を編集するカード. */
export function ManufacturerNotificationSettingsCard({
  manufacturerId,
  manufacturerEmail,
}: ManufacturerNotificationSettingsCardProps) {
  const { data, mutate } = useSWR<ManufacturerNotificationSettings>(
    `/manufacturers/${manufacturerId}/notification-settings`,
    apiClient,
  );

  const [enabled, setEnabled] = useState(false);
  const [toEmails, setToEmails] = useState<string[]>([]);
  const [ccEmails, setCcEmails] = useState<string[]>([]);
  const [initialized, setInitialized] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (data && !initialized) {
      setEnabled(data.daily_digest_enabled);
      setToEmails(data.to_emails);
      setCcEmails(data.cc_emails);
      setInitialized(true);
    }
  }, [data, initialized]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await apiClient(`/manufacturers/${manufacturerId}/notification-settings`, {
        method: "PUT",
        body: {
          daily_digest_enabled: enabled,
          to_emails: toEmails,
          cc_emails: ccEmails,
        },
      });
      toast.success("通知設定を更新しました");
      mutate();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "更新に失敗しました");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>発注通知メール（日次）</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          毎日決まった時刻に、新規の発注済み明細があるメーカーへ通知メールを送信します。
          送信時刻は「設定」画面で全社共通として設定します。
        </p>

        <div className="flex items-center gap-3">
          <Switch id="digest-enabled" checked={enabled} onCheckedChange={setEnabled} />
          <Label htmlFor="digest-enabled">このメーカーへの日次通知を有効にする</Label>
        </div>

        <EmailListInput
          id="digest-to-emails"
          label="宛先（To）"
          description={`複数登録できます。未登録の場合はメーカーのメールアドレス（${manufacturerEmail}）に送信されます。`}
          emails={toEmails}
          onChange={setToEmails}
          placeholder="例: maker@example.com"
          emptyText={`未登録（メーカーのメールアドレス ${manufacturerEmail} に送信されます）`}
        />

        <EmailListInput
          id="digest-cc-emails"
          label="CC"
          description="複数登録できます。"
          emails={ccEmails}
          onChange={setCcEmails}
          placeholder="例: cc@example.com"
          emptyText="CC は登録されていません。"
        />

        <Button onClick={handleSave} disabled={isSaving} size="sm">
          {isSaving ? "保存中..." : "保存"}
        </Button>
      </CardContent>
    </Card>
  );
}
