import useSWR from "swr";
import type { ManufacturerProfile, ManufacturerProfileUpdate } from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function getManufacturerToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("manufacturer_token");
}

async function fetchProfile(url: string): Promise<ManufacturerProfile> {
  const token = await getManufacturerToken();
  const headers: Record<string, string> = {};

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${url}`, { headers });

  if (!response.ok) {
    throw new Error("Failed to fetch profile");
  }

  return response.json();
}

export function useManufacturerProfile() {
  const { data, error, isLoading, mutate } = useSWR<ManufacturerProfile>(
    "/manufacturer-portal/profile",
    fetchProfile
  );

  return {
    profile: data,
    isLoading,
    error,
    mutate,
  };
}

export async function updateManufacturerProfile(
  data: ManufacturerProfileUpdate
): Promise<ManufacturerProfile> {
  const token = await getManufacturerToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/manufacturer-portal/profile`, {
    method: "PATCH",
    headers,
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error?.message || "プロフィールの更新に失敗しました");
  }

  return response.json();
}
