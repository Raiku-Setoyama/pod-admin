"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Paperclip, X, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { downloadFile } from "@/lib/api/client";
import type { ChatMessage } from "@/types/api";

interface ChatPanelProps {
  messages: ChatMessage[];
  onSendMessage: (content: string, files?: File[]) => void;
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

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

const ALLOWED_EXTENSIONS = [
  ".jpg", ".jpeg", ".png", ".gif", ".webp",
  ".pdf",
  ".doc", ".docx",
  ".xls", ".xlsx",
  ".txt", ".csv",
  ".zip",
];

export function ChatPanel({ messages, onSendMessage, manufacturerName, currentUserType = "admin" }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isSending, setIsSending] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() && selectedFiles.length === 0) return;

    setIsSending(true);
    try {
      onSendMessage(input.trim(), selectedFiles.length > 0 ? selectedFiles : undefined);
      setInput("");
      setSelectedFiles([]);
    } finally {
      setIsSending(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) return;

    const validFiles: File[] = [];
    for (const file of Array.from(files)) {
      if (file.size > MAX_FILE_SIZE) {
        alert(`${file.name} は10MBを超えています`);
        continue;
      }
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        alert(`${file.name} は対応していないファイル形式です`);
        continue;
      }
      validFiles.push(file);
    }
    setSelectedFiles((prev) => [...prev, ...validFiles]);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDownload = async (downloadUrl: string, filename: string) => {
    try {
      await downloadFile(downloadUrl, filename);
    } catch {
      console.error("Download failed");
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
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  {message.attachments.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {message.attachments.map((attachment) => (
                        <button
                          key={attachment.id}
                          type="button"
                          onClick={() => {
                            if (attachment.download_url) {
                              handleDownload(attachment.download_url, attachment.filename);
                            }
                          }}
                          className="flex items-center gap-1 text-xs underline cursor-pointer hover:opacity-80"
                        >
                          <Download className="h-3 w-3" />
                          {attachment.filename}
                        </button>
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
      <div className="border-t border-border bg-white p-4 space-y-3">
        {selectedFiles.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {selectedFiles.map((file, index) => (
              <div
                key={index}
                className="flex items-center gap-1 bg-muted px-2 py-1 rounded text-sm"
              >
                <Paperclip className="h-3 w-3" />
                <span className="max-w-[150px] truncate">{file.name}</span>
                <button
                  type="button"
                  onClick={() => removeFile(index)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileSelect}
            className="hidden"
            multiple
            accept={ALLOWED_EXTENSIONS.join(",")}
          />
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => fileInputRef.current?.click()}
          >
            <Paperclip className="h-4 w-4" />
          </Button>
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="メッセージを入力..."
            className="min-h-[40px] max-h-[120px] resize-none flex-1"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
          />
          <Button
            onClick={() => handleSubmit()}
            disabled={isSending || (!input.trim() && selectedFiles.length === 0)}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
