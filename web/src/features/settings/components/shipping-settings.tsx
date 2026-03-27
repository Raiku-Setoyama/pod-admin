"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";
import type { ShippingPreparationDays } from "@/types/api";

export function ShippingSettings() {
  const [days, setDays] = useState<number>(5);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSettings() {
      try {
        const data = await apiClient<ShippingPreparationDays>(
          "/settings/shipping-preparation-days"
        );
        setDays(data.value);
      } catch {
        // Use default
      } finally {
        setLoading(false);
      }
    }
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await apiClient<ShippingPreparationDays>(
        "/settings/shipping-preparation-days",
        { method: "PUT", body: { value: days } }
      );
      setMessage("保存しました");
      setTimeout(() => setMessage(null), 3000);
    } catch {
      setMessage("保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>配送設定</CardTitle>
        <CardDescription>発送準備に必要な営業日数を設定します</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-end gap-4">
          <div className="space-y-2">
            <Label htmlFor="prep-days">発送準備日数</Label>
            <div className="flex items-center gap-2">
              <Input
                id="prep-days"
                type="number"
                min={0}
                max={30}
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="w-24"
              />
              <span className="text-sm text-muted-foreground">営業日</span>
            </div>
          </div>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "保存中..." : "保存"}
          </Button>
        </div>
        {message && (
          <p className="text-sm text-muted-foreground">{message}</p>
        )}
      </CardContent>
    </Card>
  );
}
