const BASE = import.meta.env.VITE_API_URL || "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || data.detail || `Request failed (${res.status})`);
  return data;
}

export const api = {
  upload: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request("/upload/", { method: "POST", body: fd });
  },
  batches: () => request("/batches/"),
  batch: (id) => request(`/batches/${id}/`),
  urls: (params = {}) => request(`/urls/?${new URLSearchParams({ light: 1, ...params })}`),
  urlDetail: (id) => request(`/urls/${id}/`),
  search: (query, top_k = 8, use_llm = true) =>
    request("/search/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k, use_llm }),
    }),
  stats: () => request("/stats/"),
  reindex: () => request("/reindex/", { method: "POST" }),
};
