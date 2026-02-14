const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function getAuthToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

async function getManufacturerToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("manufacturer_token");
}

export async function downloadInvoiceByItems(
  manufacturerId: string,
  orderItemIds: string[]
): Promise<void> {
  const token = await getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(
    `${API_BASE_URL}/manufacturers/${manufacturerId}/invoices`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({ order_item_ids: orderItemIds }),
    }
  );

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error?.message || "請求書の発行に失敗しました");
  }

  await downloadBlobResponse(response);
}

export async function downloadPortalInvoiceByItems(
  orderItemIds: string[]
): Promise<void> {
  const token = await getManufacturerToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/manufacturer-portal/invoices`, {
    method: "POST",
    headers,
    body: JSON.stringify({ order_item_ids: orderItemIds }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error?.message || "請求書の発行に失敗しました");
  }

  await downloadBlobResponse(response);
}

async function downloadBlobResponse(response: Response): Promise<void> {
  const blob = await response.blob();

  // Get filename from Content-Disposition header
  const contentDisposition = response.headers.get("Content-Disposition");
  let filename = "請求書.pdf";
  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/);
    if (filenameMatch) {
      filename = decodeURIComponent(filenameMatch[1]);
    }
  }

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}
