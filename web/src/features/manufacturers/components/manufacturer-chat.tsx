"use client";

import { useState, useRef, useEffect } from "react";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Send, Paperclip, User, Factory, X, FileText, FileSpreadsheet, FileImage, File } from "lucide-react";
import { apiClient, downloadFile } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface ChatAttachment {
  id: string;
  filename: string;
  file_size: number;
  content_type: string;
  download_url: string | null;
}

interface ChatMessage {
  id: string;
  manufacturer_id: string;
  sender_type: "admin" | "manufacturer";
  sender_name: string;
  content: string;
  attachments: ChatAttachment[];
  created_at: string;
}

interface ChatMessagesResponse {
  items: ChatMessage[];
  total: number;
  page: number;
  limit: number;
}

interface ManufacturerChatProps {
  manufacturerId: string;
  manufacturerName: string;
}

const fetcher = (url: string) => apiClient<ChatMessagesResponse>(url);

function getFileTypeInfo(filename: string, contentType?: string): { icon: React.ReactNode; label: string; bgColor: string } {
  const ext = filename.split(".").pop()?.toLowerCase() || "";

  // Excel
  if (["xls", "xlsx"].includes(ext) || contentType?.includes("spreadsheet") || contentType?.includes("excel")) {
    return {
      icon: <FileSpreadsheet className="h-5 w-5 text-white" />,
      label: ext.toUpperCase(),
      bgColor: "bg-green-700",
    };
  }

  // CSV
  if (ext === "csv") {
    return {
      icon: <FileSpreadsheet className="h-5 w-5 text-white" />,
      label: "CSV",
      bgColor: "bg-green-700",
    };
  }

  // PDF
  if (ext === "pdf" || contentType?.includes("pdf")) {
    return {
      icon: <FileText className="h-5 w-5 text-white" />,
      label: "PDF",
      bgColor: "bg-red-600",
    };
  }

  // Word
  if (["doc", "docx"].includes(ext) || contentType?.includes("word")) {
    return {
      icon: <FileText className="h-5 w-5 text-white" />,
      label: ext.toUpperCase(),
      bgColor: "bg-blue-600",
    };
  }

  // Image
  if (["jpg", "jpeg", "png", "gif", "webp"].includes(ext) || contentType?.startsWith("image/")) {
    return {
      icon: <FileImage className="h-5 w-5 text-white" />,
      label: ext.toUpperCase(),
      bgColor: "bg-purple-600",
    };
  }

  // Text
  if (ext === "txt" || contentType?.includes("text/plain")) {
    return {
      icon: <FileText className="h-5 w-5 text-white" />,
      label: "TXT",
      bgColor: "bg-gray-600",
    };
  }

  // ZIP
  if (ext === "zip" || contentType?.includes("zip")) {
    return {
      icon: <File className="h-5 w-5 text-white" />,
      label: "ZIP",
      bgColor: "bg-yellow-600",
    };
  }

  // Default
  return {
    icon: <File className="h-5 w-5 text-white" />,
    label: ext ? ext.toUpperCase() : "FILE",
    bgColor: "bg-gray-500",
  };
}

export function ManufacturerChat({ manufacturerId, manufacturerName }: ManufacturerChatProps) {
  const [message, setMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data, mutate } = useSWR<ChatMessagesResponse>(
    `/chat/manufacturers/${manufacturerId}?limit=100`,
    fetcher,
    { refreshInterval: 5000 }
  );

  const messages = data?.items ?? [];

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  const handleSend = async () => {
    if (!message.trim() && selectedFiles.length === 0) return;

    setIsSending(true);
    try {
      const formData = new FormData();
      formData.append("content", message);
      selectedFiles.forEach((file) => {
        formData.append("attachments", file);
      });

      await apiClient(`/chat/manufacturers/${manufacturerId}`, {
        method: "POST",
        body: formData,
      });

      setMessage("");
      setSelectedFiles([]);
      mutate();
    } catch (error) {
      console.error("Failed to send message:", error);
    } finally {
      setIsSending(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      setSelectedFiles((prev) => [...prev, ...Array.from(files)]);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString("ja-JP", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <Card className="flex flex-col h-[600px]">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <Factory className="h-5 w-5" />
          {manufacturerName} とのチャット
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col p-0">
        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
          <div className="space-y-4">
            {messages.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                まだメッセージがありません
              </div>
            ) : (
              messages.map((msg) => {
                const isAdmin = msg.sender_type === "admin";
                return (
                  <div key={msg.id} className="space-y-2">
                    {/* Text content */}
                    {msg.content && (
                      <div
                        className={cn(
                          "flex gap-3",
                          isAdmin && "flex-row-reverse"
                        )}
                      >
                        <div
                          className={cn(
                            "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                            isAdmin
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted"
                          )}
                        >
                          {isAdmin ? (
                            <User className="h-4 w-4" />
                          ) : (
                            <Factory className="h-4 w-4" />
                          )}
                        </div>
                        <div
                          className={cn(
                            "max-w-[70%] space-y-1",
                            isAdmin && "text-right"
                          )}
                        >
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span>{msg.sender_name}</span>
                            <span>{formatTime(msg.created_at)}</span>
                          </div>
                          <div
                            className={cn(
                              "p-3 rounded-lg",
                              isAdmin
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted"
                            )}
                          >
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Attachments as separate items */}
                    {msg.attachments.map((att) => {
                      const fileInfo = getFileTypeInfo(att.filename, att.content_type);
                      return (
                        <div
                          key={att.id}
                          className={cn(
                            "flex gap-3",
                            isAdmin && "flex-row-reverse"
                          )}
                        >
                          <div className="w-8 flex-shrink-0" />
                          <div
                            className={cn(
                              "max-w-[70%] space-y-1",
                              isAdmin && "text-right"
                            )}
                          >
                            {!msg.content && (
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <span>{msg.sender_name}</span>
                                <span>{formatTime(msg.created_at)}</span>
                              </div>
                            )}
                            <button
                              type="button"
                              onClick={() => {
                                if (att.download_url) {
                                  downloadFile(att.download_url, att.filename);
                                }
                              }}
                              className="flex items-center gap-3 rounded-lg bg-muted p-3 cursor-pointer hover:bg-muted/80 transition-colors"
                            >
                              <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg shrink-0", fileInfo.bgColor)}>
                                {fileInfo.icon}
                              </div>
                              <div className="flex-1 min-w-0 text-left">
                                <p className="text-sm font-medium truncate text-foreground">
                                  {att.filename}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {fileInfo.label}
                                </p>
                              </div>
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })
            )}
          </div>
        </ScrollArea>

        <div className="border-t p-4 space-y-3">
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
            />
            <Button
              variant="outline"
              size="icon"
              onClick={() => fileInputRef.current?.click()}
            >
              <Paperclip className="h-4 w-4" />
            </Button>
            <Textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="メッセージを入力..."
              className="min-h-[40px] max-h-[120px] resize-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
            />
            <Button onClick={handleSend} disabled={isSending}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
