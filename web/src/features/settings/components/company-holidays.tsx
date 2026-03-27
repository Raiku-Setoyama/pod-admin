"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
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
import { apiClient } from "@/lib/api/client";
import type { CompanyHoliday, CompanyHolidayListResponse } from "@/types/api";

export function CompanyHolidays() {
  const [holidays, setHolidays] = useState<CompanyHoliday[]>([]);
  const [loading, setLoading] = useState(true);
  const [newDate, setNewDate] = useState("");
  const [newName, setNewName] = useState("");
  const [adding, setAdding] = useState(false);

  const fetchHolidays = useCallback(async () => {
    try {
      const data = await apiClient<CompanyHolidayListResponse>(
        "/settings/company-holidays"
      );
      setHolidays(data.items);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHolidays();
  }, [fetchHolidays]);

  const handleAdd = async () => {
    if (!newDate || !newName) return;
    setAdding(true);
    try {
      await apiClient<CompanyHoliday>("/settings/company-holidays", {
        method: "POST",
        body: { date: newDate, name: newName },
      });
      setNewDate("");
      setNewName("");
      await fetchHolidays();
    } catch (error) {
      alert(error instanceof Error ? error.message : "追加に失敗しました");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiClient<void>(`/settings/company-holidays/${id}`, {
        method: "DELETE",
      });
      await fetchHolidays();
    } catch (error) {
      alert(error instanceof Error ? error.message : "削除に失敗しました");
    }
  };

  if (loading) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>会社休日</CardTitle>
        <CardDescription>
          TOSYO独自の休日を登録します。配送予定日の計算から除外されます。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-end gap-4">
          <div className="space-y-2">
            <Label htmlFor="holiday-date">日付</Label>
            <Input
              id="holiday-date"
              type="date"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
              className="w-44"
            />
          </div>
          <div className="space-y-2 flex-1">
            <Label htmlFor="holiday-name">休日名</Label>
            <Input
              id="holiday-name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="例: 夏季休暇"
            />
          </div>
          <Button onClick={handleAdd} disabled={adding || !newDate || !newName}>
            {adding ? "追加中..." : "追加"}
          </Button>
        </div>

        {holidays.length > 0 && (
          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>日付</TableHead>
                  <TableHead>休日名</TableHead>
                  <TableHead className="w-[80px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {holidays.map((holiday) => (
                  <TableRow key={holiday.id}>
                    <TableCell>{holiday.date}</TableCell>
                    <TableCell>{holiday.name}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(holiday.id)}
                        className="text-destructive hover:text-destructive"
                      >
                        削除
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {holidays.length === 0 && (
          <p className="text-sm text-muted-foreground">登録された休日はありません</p>
        )}
      </CardContent>
    </Card>
  );
}
