import { useState, useEffect, useCallback } from "react";
import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { ChatMessageListResponse } from "@/types/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const fetcher = async (url: string) => {
  const token = localStorage.getItem("manufacturer_token");
  if (!token) {
    throw new Error("No authentication token");
  }
  return apiClient<ChatMessageListResponse>(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
};

export function useManufacturerChat() {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const storedToken = localStorage.getItem("manufacturer_token");
    setToken(storedToken);
  }, []);

  const { data, error, isLoading, mutate } = useSWR<ChatMessageListResponse>(
    token ? `/manufacturer-portal/chat` : null,
    fetcher,
    {
      refreshInterval: 5000,
    }
  );

  const sendMessage = useCallback(async (content: string) => {
    const storedToken = localStorage.getItem("manufacturer_token");
    if (!storedToken) {
      throw new Error("No authentication token");
    }

    const formData = new FormData();
    formData.append("content", content);

    const response = await fetch(`${API_URL}/manufacturer-portal/chat`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${storedToken}`,
      },
      body: formData,
    });

    if (!response.ok) {
      throw new Error("Failed to send message");
    }

    await mutate();
    return response.json();
  }, [mutate]);

  return {
    messages: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading: token === null || isLoading,
    error,
    sendMessage,
    mutate,
  };
}
