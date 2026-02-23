"use client";

import { PageContainer } from "@/components/layout/page-container";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

export default function SettingsPage() {
  return (
    <PageContainer title="設定" description="アカウント設定">
      <div className="max-w-2xl space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>アカウント情報</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">メールアドレス</Label>
              <Input id="email" defaultValue="admin@example.com" disabled />
            </div>
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}
