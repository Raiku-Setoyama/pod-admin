"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface EmailListInputProps {
  id: string;
  label: string;
  description?: string;
  emails: string[];
  onChange: (emails: string[]) => void;
  placeholder: string;
  emptyText: string;
}

/**
 * バッジ形式で複数メールアドレスを追加・削除できる入力欄。
 * 追加時に形式・重複を検証し、エラーはコンポーネント内部で表示する。
 */
export function EmailListInput({
  id,
  label,
  description,
  emails,
  onChange,
  placeholder,
  emptyText,
}: EmailListInputProps) {
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleAdd = () => {
    const email = input.trim();
    if (!email) return;
    if (!EMAIL_REGEX.test(email)) {
      setError(`メールアドレスの形式が正しくありません: ${email}`);
      return;
    }
    if (emails.includes(email)) {
      setError("既に登録されているメールアドレスです");
      return;
    }
    onChange([...emails, email]);
    setInput("");
    setError(null);
  };

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
      <div className="flex items-end gap-3">
        <Input
          id={id}
          type="email"
          placeholder={placeholder}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              handleAdd();
            }
          }}
        />
        <Button type="button" onClick={handleAdd} variant="secondary" size="sm">
          <Plus className="h-4 w-4 mr-1" />
          追加
        </Button>
      </div>

      {emails.length > 0 ? (
        <div className="flex flex-wrap gap-2 pt-1">
          {emails.map((email) => (
            <Badge key={email} variant="secondary" className="gap-1 pr-1">
              {email}
              <button
                type="button"
                aria-label={`${email} を削除`}
                onClick={() => onChange(emails.filter((x) => x !== email))}
                className="rounded-full p-0.5 hover:bg-muted-foreground/20"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyText}</p>
      )}

      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
