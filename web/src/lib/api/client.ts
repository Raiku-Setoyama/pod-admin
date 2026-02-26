const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  skipAuth?: boolean;
};

class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// トークンリフレッシュの排他制御用
let refreshPromise: Promise<boolean> | null = null;

async function getAuthToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

export function clearTokens(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  const currentPath = window.location.pathname;
  window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`;
}

/**
 * JWTトークンのペイロードをデコード
 */
function decodeJwtPayload(token: string): { exp?: number } | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = parts[1];
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

/**
 * トークンが有効期限切れかどうかをチェック
 * @param bufferSeconds - 有効期限の何秒前から期限切れとみなすか（デフォルト: 60秒）
 */
export function isTokenExpired(token: string | null, bufferSeconds = 60): boolean {
  if (!token) return true;

  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return true;

  const now = Math.floor(Date.now() / 1000);
  return payload.exp - bufferSeconds <= now;
}

/**
 * トークンリフレッシュを試みる（外部から呼び出し可能）
 */
export { refreshAccessToken };

async function refreshAccessToken(): Promise<boolean> {
  // 既にリフレッシュ中の場合は同じPromiseを返す（排他制御）
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      return false;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        return false;
      }

      const data = await response.json();
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

async function executeRequest<T>(
  endpoint: string,
  options: RequestOptions
): Promise<Response> {
  const { method = "GET", body, headers = {}, skipAuth = false } = options;

  const token = await getAuthToken();
  const requestHeaders: Record<string, string> = {};

  // デフォルトのトークンを設定（access_token）
  if (token && !skipAuth) {
    requestHeaders["Authorization"] = `Bearer ${token}`;
  }

  // 渡されたheadersで上書き（manufacturer_tokenなど）
  Object.assign(requestHeaders, headers);

  if (body && !(body instanceof FormData)) {
    requestHeaders["Content-Type"] = "application/json";
  }

  return fetch(`${API_BASE_URL}${endpoint}`, {
    method,
    headers: requestHeaders,
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  });
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  let response = await executeRequest<T>(endpoint, options);

  // 401エラーの場合、トークンリフレッシュを試みる
  if (response.status === 401 && !options.skipAuth) {
    const refreshed = await refreshAccessToken();

    if (refreshed) {
      // リフレッシュ成功：リクエストをリトライ
      response = await executeRequest<T>(endpoint, options);
    } else {
      // リフレッシュ失敗：トークンをクリアしてログインページへ
      clearTokens();
      redirectToLogin();
      throw new ApiError(401, "UNAUTHORIZED", "セッションが期限切れです。再度ログインしてください。");
    }
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorData.error?.code || "UNKNOWN_ERROR",
      errorData.error?.message || "An error occurred",
      errorData.error?.details
    );
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

async function executeDownloadRequest(endpoint: string): Promise<Response> {
  const token = await getAuthToken();
  const headers: Record<string, string> = {};

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return fetch(`${API_BASE_URL}${endpoint}`, { headers });
}

export async function downloadFile(endpoint: string, filename: string): Promise<void> {
  let response = await executeDownloadRequest(endpoint);

  // 401エラーの場合、トークンリフレッシュを試みる
  if (response.status === 401) {
    const refreshed = await refreshAccessToken();

    if (refreshed) {
      // リフレッシュ成功：リクエストをリトライ
      response = await executeDownloadRequest(endpoint);
    } else {
      // リフレッシュ失敗：トークンをクリアしてログインページへ
      clearTokens();
      redirectToLogin();
      throw new Error("セッションが期限切れです。再度ログインしてください。");
    }
  }

  if (!response.ok) {
    throw new Error("Download failed");
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export async function downloadFileByPost(
  endpoint: string,
  body: unknown,
  filename: string
): Promise<void> {
  const token = await getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error("Download failed");
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export { ApiError };
