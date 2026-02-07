"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Paperclip } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/api";

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (content: string) => void;
  manufacturerName: string;
  currentUserType?: "admin" | "manufacturer";
}

function formatTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ChatPanel({ messages, onSendMessage, manufacturerName, currentUserType = "admin" }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      onSendMessage(input.trim());
      setInput("");
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border bg-white px-4 py-3">
        <h3 className="font-semibold">{manufacturerName}</h3>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 p-4" ref={scrollRef}>
        <div className="space-y-4">
          {messages.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground">
              メッセージはありません
            </p>
          ) : (
            messages.map((message) => {
              const isCurrentUser = message.sender_type === currentUserType;
              return (
              <div
                key={message.id}
                className={cn(
                  "flex flex-col",
                  isCurrentUser ? "items-end" : "items-start"
                )}
              >
                <div
                  className={cn(
                    "max-w-[70%] rounded-lg px-4 py-2",
                    isCurrentUser
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  )}
                >
                  <p className="text-sm">{message.content}</p>
                  {message.attachments.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {message.attachments.map((attachment) => (
                        <a
                          key={attachment.id}
                          href={attachment.file_path}
                          className="flex items-center gap-1 text-xs underline"
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <Paperclip className="h-3 w-3" />
                          {attachment.filename}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
                <span className="mt-1 text-xs text-muted-foreground">
                  {message.sender_name} - {formatTime(message.created_at)}
                </span>
              </div>
            );
            })
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-border bg-white p-4"
      >
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="icon">
            <Paperclip className="h-4 w-4" />
          </Button>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="メッセージを入力..."
            className="flex-1"
          />
          <Button type="submit" disabled={!input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
