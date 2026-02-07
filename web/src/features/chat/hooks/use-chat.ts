import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { ChatMessageListResponse, Manufacturer } from "@/types/api";

interface UseChatParams {
  manufacturerId: string;
  page?: number;
  limit?: number;
}

export function useChat(params: UseChatParams) {
  const { manufacturerId, page = 1, limit = 50 } = params;

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("limit", String(limit));

  const { data, error, isLoading, mutate } = useSWR<ChatMessageListResponse>(
    manufacturerId
      ? `/manufacturers/${manufacturerId}/chat?${queryParams.toString()}`
      : null,
    apiClient
  );

  return {
    messages: data?.items ?? [],
    total: data?.total ?? 0,
    isLoading,
    error,
    mutate,
  };
}

export function useManufacturerList() {
  const { data, error, isLoading } = useSWR<{ items: Manufacturer[] }>(
    "/manufacturers?limit=100",
    apiClient
  );

  return {
    manufacturers: data?.items ?? [],
    isLoading,
    error,
  };
}
