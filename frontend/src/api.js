import { API_BASE } from "./config";

async function req(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  listEquipment: () => req("/equipment"),
  getEquipment: (id) => req(`/equipment/${id}`),
  listDocuments: () => req("/documents"),
  reviewQueue: () => req("/review-queue"),
  listNotifications: () => req("/notifications"),
  recompute: (ref_date) =>
    req("/admin/recompute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref_date: ref_date || null }),
    }),
  approve: (docId, body) =>
    req(`/documents/${docId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }),
  upload: (file) => {
    const form = new FormData();
    form.append("file", file);
    return req("/documents/upload", { method: "POST", body: form });
  },
  fileUrl: (docId) => `${API_BASE}/documents/${docId}/file`,
};
