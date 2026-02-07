"use client";

import { PageContainer } from "@/components/layout/page-container";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

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
            <div className="space-y-2">
              <Label htmlFor="name">名前</Label>
              <Input id="name" defaultValue="管理者" />
            </div>
            <Button>保存</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>パスワード変更</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current-password">現在のパスワード</Label>
              <Input id="current-password" type="password" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-password">新しいパスワード</Label>
              <Input id="new-password" type="password" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">新しいパスワード（確認）</Label>
              <Input id="confirm-password" type="password" />
            </div>
            <Button>パスワードを変更</Button>
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}
