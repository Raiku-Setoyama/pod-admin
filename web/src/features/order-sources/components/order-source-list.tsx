"use client";

import { useState } from "react";
import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { OrderSourceFormDialog } from "./order-source-form-dialog";
import { OrderSourceDeleteDialog } from "./order-source-delete-dialog";
import type { OrderSource, OrderSourceListResponse } from "@/types/api";

function maskApiKey(apiKey: string): string {
  if (apiKey.length <= 4) {
    return "****";
  }
  return apiKey.slice(0, 4) + "****";
}

export function OrderSourceList() {
  const { data, isLoading, mutate } = useSWR<OrderSourceListResponse>(
    "/order-sources?page=1&limit=20",
    apiClient
  );

  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<OrderSource | undefined>(
    undefined
  );
  const [deleteTarget, setDeleteTarget] = useState<OrderSource | undefined>(
    undefined
  );

  const handleCreateClick = () => {
    setEditTarget(undefined);
    setFormOpen(true);
  };

  const handleEditClick = (source: OrderSource) => {
    setEditTarget(source);
    setFormOpen(true);
  };

  const handleDeleteClick = (source: OrderSource) => {
    setDeleteTarget(source);
  };

  const handleFormSuccess = () => {
    setFormOpen(false);
    setEditTarget(undefined);
    mutate();
  };

  const handleFormClose = () => {
    setFormOpen(false);
    setEditTarget(undefined);
  };

  const handleDeleteSuccess = () => {
    setDeleteTarget(undefined);
    mutate();
  };

  const handleDeleteClose = () => {
    setDeleteTarget(undefined);
  };

  const items = data?.items ?? [];

  if (isLoading) {
    return (
      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">受注元一覧</h2>
          <Button onClick={handleCreateClick}>
            <Plus className="mr-1 h-4 w-4" />
            新規登録
          </Button>
        </div>
        <div className="flex items-center justify-center py-12">
          <span className="text-muted-foreground">読み込み中...</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">受注元一覧</h2>
        <Button onClick={handleCreateClick}>
          <Plus className="mr-1 h-4 w-4" />
          新規登録
        </Button>
      </div>

      {items.length === 0 ? (
        <div className="flex items-center justify-center rounded-lg border py-12">
          <p className="text-muted-foreground">データがありません</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">コード</th>
                <th className="px-4 py-3 text-left font-medium">名前</th>
                <th className="px-4 py-3 text-left font-medium">電話番号</th>
                <th className="px-4 py-3 text-left font-medium">住所</th>
                <th className="px-4 py-3 text-left font-medium">APIキー</th>
                <th className="px-4 py-3 text-left font-medium">状態</th>
                <th className="px-4 py-3 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((source) => (
                <tr key={source.id} className="border-b">
                  <td className="px-4 py-3">{source.code}</td>
                  <td className="px-4 py-3">{source.name}</td>
                  <td className="px-4 py-3">{source.phone}</td>
                  <td className="px-4 py-3">
                    {source.address_prefecture}
                    {source.address_city}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {maskApiKey(source.api_key)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                        source.is_active
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {source.is_active ? "有効" : "無効"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleEditClick(source)}
                      >
                        <Pencil className="h-4 w-4" />
                        編集
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteClick(source)}
                      >
                        <Trash2 className="h-4 w-4" />
                        削除
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <OrderSourceFormDialog
        open={formOpen}
        orderSource={editTarget}
        onClose={handleFormClose}
        onSuccess={handleFormSuccess}
      />

      {deleteTarget && (
        <OrderSourceDeleteDialog
          open={!!deleteTarget}
          orderSource={deleteTarget}
          onClose={handleDeleteClose}
          onSuccess={handleDeleteSuccess}
        />
      )}
    </div>
  );
}
