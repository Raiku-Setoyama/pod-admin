/**
 * Sidebar コンポーネントのユニットテスト
 *
 * Intent Spec: FEAT-0001
 * AC-001: サイドバーにログインユーザーのメールアドレスが表示される
 * AC-005: 固定メールアドレス「raiku6019@gmail.com」が削除されている
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Sidebar } from "@/components/layout/sidebar";
import React from "react";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/orders",
}));

// Mock useCurrentUser フック
vi.mock("@/features/auth/hooks/use-current-user", () => ({
  useCurrentUser: vi.fn(),
}));

import { useCurrentUser } from "@/features/auth/hooks/use-current-user";

const mockUseCurrentUser = vi.mocked(useCurrentUser);

describe("Sidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // localStorage のモック
    Object.defineProperty(window, "localStorage", {
      value: {
        getItem: vi.fn(),
        setItem: vi.fn(),
        removeItem: vi.fn(),
      },
      writable: true,
    });
  });

  describe("AC-001: ログインユーザーのメールアドレス表示", () => {
    it("ログインユーザーのメールアドレスがサイドバーに表示される", () => {
      mockUseCurrentUser.mockReturnValue({
        user: {
          id: "user-1",
          email: "current.user@example.com",
          name: "Current User",
          role: "admin",
          is_active: true,
        },
        isLoading: false,
        error: undefined,
        mutate: vi.fn(),
      });

      render(<Sidebar />);

      expect(screen.getByText("current.user@example.com")).toBeInTheDocument();
    });

    it("異なるユーザーのメールアドレスも正しく表示される", () => {
      mockUseCurrentUser.mockReturnValue({
        user: {
          id: "user-2",
          email: "another.admin@company.co.jp",
          name: "Another Admin",
          role: "staff",
          is_active: true,
        },
        isLoading: false,
        error: undefined,
        mutate: vi.fn(),
      });

      render(<Sidebar />);

      expect(screen.getByText("another.admin@company.co.jp")).toBeInTheDocument();
    });
  });

  describe("AC-003: ローディング状態", () => {
    it("ローディング中はスケルトンまたは空が表示される", () => {
      mockUseCurrentUser.mockReturnValue({
        user: undefined,
        isLoading: true,
        error: undefined,
        mutate: vi.fn(),
      });

      render(<Sidebar />);

      // ハードコードされたメールが表示されていないこと
      expect(screen.queryByText("raiku6019@gmail.com")).not.toBeInTheDocument();
    });
  });

  describe("AC-004: エラー時のフォールバック", () => {
    it("エラー時はメールアドレス部分が空またはフォールバック表示", () => {
      mockUseCurrentUser.mockReturnValue({
        user: undefined,
        isLoading: false,
        error: new Error("Failed to fetch"),
        mutate: vi.fn(),
      });

      render(<Sidebar />);

      // ハードコードされたメールが表示されていないこと
      expect(screen.queryByText("raiku6019@gmail.com")).not.toBeInTheDocument();
    });
  });

  describe("AC-005: ハードコードされたメールアドレスの削除", () => {
    it("固定メールアドレス「raiku6019@gmail.com」が表示されない", () => {
      mockUseCurrentUser.mockReturnValue({
        user: {
          id: "user-1",
          email: "dynamic@example.com",
          name: "Dynamic User",
          role: "admin",
          is_active: true,
        },
        isLoading: false,
        error: undefined,
        mutate: vi.fn(),
      });

      render(<Sidebar />);

      // ハードコードされたメールアドレスが存在しないことを確認
      expect(screen.queryByText("raiku6019@gmail.com")).not.toBeInTheDocument();
    });

    it("コンポーネント内にハードコードされたメールが含まれていない", () => {
      mockUseCurrentUser.mockReturnValue({
        user: undefined,
        isLoading: false,
        error: undefined,
        mutate: vi.fn(),
      });

      render(<Sidebar />);

      // ユーザー未取得時もハードコードメールが表示されない
      expect(screen.queryByText("raiku6019@gmail.com")).not.toBeInTheDocument();
    });
  });

  describe("サイドバーの基本機能", () => {
    it("ナビゲーションリンクが表示される", () => {
      mockUseCurrentUser.mockReturnValue({
        user: {
          id: "user-1",
          email: "test@example.com",
          name: "Test User",
          role: "admin",
          is_active: true,
        },
        isLoading: false,
        error: undefined,
        mutate: vi.fn(),
      });

      render(<Sidebar />);

      expect(screen.getByText("受注")).toBeInTheDocument();
      expect(screen.getByText("発注")).toBeInTheDocument();
      expect(screen.getByText("配送")).toBeInTheDocument();
      expect(screen.getByText("メーカー")).toBeInTheDocument();
      expect(screen.getByText("商品マスタ")).toBeInTheDocument();
      expect(screen.getByText("設定")).toBeInTheDocument();
      expect(screen.getByText("ログアウト")).toBeInTheDocument();
    });
  });
});
