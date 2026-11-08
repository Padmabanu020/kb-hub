import { useEffect, useState } from "react";
import { api } from "../api";

export default function UrlTable() {
  const [data, setData] = useState({ results: [], count: 0 });
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const params = { page };
    if (q) params.q = q;
    if (status) params.http_status = status;
    api.urls(params).then(setData).catch((e) => setError(e.message));
  }, [page, q, status]);

  const pages = Math.max(1, Math.ceil(data.count / 25));
  const show = async (id) => setOpen(await api.urlDetail(id));

  return (
    <section>
      <div className="row">
        <input placeholder="Filter by URL or title…" value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} />
        <select value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
          <option value="">All statuses</option>
          <option value="200">200</option><option value="403">403</option>
          <option value="404">404</option><option value="500">500</option>
        </select>
        <a className="muted" href="/api/urls/" target="_blank" rel="noreferrer">GET /api/urls/ ↗</a>
      </div>
      {error && <p className="error">{error}</p>}
      <table>
        <thead><tr><th>URL</th><th>Status</th><th>Title</th><th>Chunks</th><th /></tr></thead>
        <tbody>
          {data.results.map((r) => (
            <tr key={r.id}>
              <td className="url"><a href={r.url} target="_blank" rel="noreferrer">{r.url}</a></td>
              <td><span className={`pill s${String(r.http_status || "err")[0]}`}>{r.http_status ?? (r.fetched_at ? "error" : "pending")}</span></td>
              <td>{r.title || <span className="muted">{r.error?.slice(0, 60)}</span>}</td>
              <td>{r.chunk_count}</td>
              <td><button onClick={() => show(r.id)}>Details</button></td>
            </tr>
          ))}
          {!data.results.length && <tr><td colSpan="5" className="muted">Nothing here yet — upload a CSV first.</td></tr>}
        </tbody>
      </table>
      <div className="row">
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</button>
        <span className="muted">Page {page} / {pages} · {data.count} URLs</span>
        <button disabled={page >= pages} onClick={() => setPage(page + 1)}>Next →</button>
      </div>

      {open && (
        <div className="modal" onClick={() => setOpen(null)}>
          <div className="modal-body" onClick={(e) => e.stopPropagation()}>
            <div className="row"><h3>{open.title || open.url}</h3><button onClick={() => setOpen(null)}>Close</button></div>
            <p className="muted">{open.final_url || open.url} · HTTP {open.http_status ?? "—"} · {open.content_type}</p>
            {open.error && <p className="error">{open.error}</p>}
            <h4>Metadata</h4>
            <pre>{JSON.stringify(open.metadata, null, 2)}</pre>
            <h4>Raw content (first 5,000 chars)</h4>
            <pre>{(open.raw_content || "").slice(0, 5000)}</pre>
          </div>
        </div>
      )}
    </section>
  );
}
