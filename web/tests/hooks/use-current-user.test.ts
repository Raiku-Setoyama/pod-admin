/**
 * useCurrentUser フックのユニットテスト
 *
 * Intent Spec: FEAT-0001
 * AC-002: useCurrentUserフックが/auth/meエンドポイントからユーザー情報を取得する
 * AC-003: ユーザー情報取得中はローディング状態が表示される
 * AC-004: ユーザー情報取得に失敗した場合のエラーハンドリング
 */
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useCurrentUser } from "@/features/auth/hooks/use-current-user";

// Mock SWR
vi.mock("swr", () => ({
  default: vi.fn(),
}));

// Mock apiClient
vi.mock("@/lib/api/client", () => ({
  apiClient: vi.fn(),
}));

import useSWR from "swr";
import { apiClient } from "@/lib/api/client";

const mockUseSWR = vi.mocked(useSWR);
const mockApiClient = vi.mocked(apiClient);

describe("useCurrentUser", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("AC-002: /auth/me からユーザー情報を取得", () => {
    it("ユーザー情報を正常に取得できる", async () => {
      const mockUser = {
        id: "user-1",
        email: "test@example.com",
        name: "Test User",
        role: "admin" as const,
        is_active: true,
      };

      mockUseSWR.mockReturnValue({
        data: mockUser,
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      });

      const { result } = renderHook(() => useCurrentUser());

      expect(result.current.user).toEqual(mockUser);
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeUndefined();
    });

    it("/auth/me エンドポイントを呼び出す", () => {
      mockUseSWR.mockReturnValue({
        data: undefined,
        error: undefined,
        isLoading: true,
        isValidating: false,
        mutate: vi.fn(),
      });

      renderHook(() => useCurrentUser());

      expect(mockUseSWR).toHaveBeenCalledWith(
        "/auth/me",
        expect.any(Function),
        expect.any(Object)
      );
    });

    it("emailフィールドが取得できる", () => {
      const mockUser = {
        id: "user-1",
        email: "admin@company.com",
        name: "Admin User",
        role: "admin" as const,
        is_active: true,
      };

      mockUseSWR.mockReturnValue({
        data: mockUser,
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      });

      const { result } = renderHook(() => useCurrentUser());

      expect(result.current.user?.email).toBe("admin@company.com");
    });
  });

  describe("AC-003: ローディング状態", () => {
    it("API呼び出し中はisLoading=trueが返される", () => {
      mockUseSWR.mockReturnValue({
        data: undefined,
        error: undefined,
        isLoading: true,
        isValidating: false,
        mutate: vi.fn(),
      });

      const { result } = renderHook(() => useCurrentUser());

      expect(result.current.isLoading).toBe(true);
      expect(result.current.user).toBeUndefined();
    });

    it("API呼び出し完了後はisLoading=falseになる", () => {
      mockUseSWR.mockReturnValue({
        data: { id: "1", email: "test@example.com", name: "Test", role: "admin", is_active: true },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      });

      const { result } = renderHook(() => useCurrentUser());

      expect(result.current.isLoading).toBe(false);
    });
  });

  describe("AC-004: エラーハンドリング", () => {
    it("APIエラー時にerrorオブジェクトが返される", () => {
      const mockError = new Error("Unauthorized");

      mockUseSWR.mockReturnValue({
        data: undefined,
        error: mockError,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      });

      const { result } = renderHook(() => useCurrentUser());

      expect(result.current.error).toEqual(mockError);
      expect(result.current.user).toBeUndefined();
    });

    it("401エラー時もエラー状態になる", () => {
      const authError = {
        status: 401,
        code: "UNAUTHORIZED",
        message: "Token expired",
      };

      mockUseSWR.mockReturnValue({
        data: undefined,
        error: authError,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      });

      const { result } = renderHook(() => useCurrentUser());

      expect(result.current.error).toBeDefined();
      expect(result.current.isLoading).toBe(false);
    });
  });
});
