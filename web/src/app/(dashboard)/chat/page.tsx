"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/layout/page-container";
import { PageLoading } from "@/components/common/loading-spinner";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatPanel } from "@/features/chat/components/chat-panel";
import { useChat, useManufacturerList } from "@/features/chat/hooks/use-chat";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";

function ChatContent() {
  const searchParams = useSearchParams();
  const [selectedManufacturerId, setSelectedManufacturerId] = useState<string | null>(
    searchParams.get("manufacturer")
  );

  const { manufacturers, isLoading: isLoadingManufacturers } = useManufacturerList();
  const { messages, mutate } = useChat({
    manufacturerId: selectedManufacturerId || "",
  });

  useEffect(() => {
    const manufacturerParam = searchParams.get("manufacturer");
    if (manufacturerParam) {
      setSelectedManufacturerId(manufacturerParam);
    }
  }, [searchParams]);

  const selectedManufacturer = manufacturers.find(
    (m) => m.id === selectedManufacturerId
  );

  const handleSendMessage = async (content: string, files?: File[]) => {
    if (!selectedManufacturerId) return;

    try {
      const formData = new FormData();
      formData.append("content", content);
      if (files) {
        files.forEach((file) => {
          formData.append("attachments", file);
        });
      }

      await apiClient(`/chat/manufacturers/${selectedManufacturerId}`, {
        method: "POST",
        body: formData,
      });
      mutate();
    } catch (error) {
      console.error("Failed to send message:", error);
    }
  };

  if (isLoadingManufacturers) {
    return (
      <PageContainer title="チャット" description="メーカーとのメッセージ">
        <PageLoading />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="チャット" description="メーカーとのメッセージ">
      <div className="flex h-[calc(100vh-180px)] rounded-lg border border-border bg-white">
        {/* Manufacturer list */}
        <div className="w-64 border-r border-border">
          <div className="border-b border-border px-4 py-3">
            <h3 className="text-sm font-semibold text-muted-foreground">
              メーカー一覧
            </h3>
          </div>
          <ScrollArea className="h-[calc(100%-48px)]">
            <div className="p-2">
              {manufacturers.map((manufacturer) => (
                <button
                  key={manufacturer.id}
                  onClick={() => setSelectedManufacturerId(manufacturer.id)}
                  className={cn(
                    "w-full rounded-lg px-3 py-2 text-left text-sm transition-colors",
                    selectedManufacturerId === manufacturer.id
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-accent"
                  )}
                >
                  {manufacturer.name}
                </button>
              ))}
            </div>
          </ScrollArea>
        </div>

        {/* Chat panel */}
        <div className="flex-1">
          {selectedManufacturer ? (
            <ChatPanel
              messages={messages}
              onSendMessage={handleSendMessage}
              manufacturerName={selectedManufacturer.name}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              メーカーを選択してください
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={
      <PageContainer title="チャット" description="メーカーとのメッセージ">
        <PageLoading />
      </PageContainer>
    }>
      <ChatContent />
    </Suspense>
  );
}
