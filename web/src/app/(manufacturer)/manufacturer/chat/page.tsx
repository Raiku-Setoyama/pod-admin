"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingSpinner } from "@/components/common/loading-spinner";
import { ChatPanel } from "@/features/chat/components/chat-panel";
import { useManufacturerChat } from "@/features/manufacturer-portal/hooks/use-manufacturer-chat";
import { MessageSquare } from "lucide-react";

export default function ManufacturerChatPage() {
  const [manufacturerName, setManufacturerName] = useState<string | null>(null);
  const { messages, isLoading, sendMessage } = useManufacturerChat();

  useEffect(() => {
    const name = localStorage.getItem("manufacturer_name");
    setManufacturerName(name);
  }, []);

  const handleSendMessage = async (content: string) => {
    try {
      await sendMessage(content);
    } catch (error) {
      console.error("Failed to send message:", error);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <MessageSquare className="h-6 w-6" />
          チャット
        </h2>
        <p className="text-muted-foreground">
          管理者とのメッセージのやり取り
        </p>
      </div>

      <Card className="h-[calc(100vh-250px)]">
        <CardContent className="h-full p-0">
          {isLoading ? (
            <div className="flex h-full items-center justify-center">
              <LoadingSpinner />
            </div>
          ) : (
            <ChatPanel
              messages={messages}
              onSendMessage={handleSendMessage}
              manufacturerName={manufacturerName || "管理者"}
              currentUserType="manufacturer"
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
