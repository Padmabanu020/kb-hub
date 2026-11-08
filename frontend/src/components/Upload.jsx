import { useEffect, useRef, useState } from "react";
import { api } from "../api";

export default function Upload({ onDone, goToUrls }) {
  const [file, setFile] = useState(null);
  const [batch, setBatch] = useState(null);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const timer = useRef(null);

  const loadBatches = () => api.batches().then((d) => setBatches(d.results || [])).catch(() => {});
  useEffect(() => { loadBatches(); return () => clearInterval(timer.current); }, []);

  const poll = (id) => {
    clearInterval(timer.current);
    timer.current = setInterval(async () => {
      try {
        const b = await api.batch(id);
        setBatch(b);
        if (b.status === "done" || b.status === "failed") {
          clearInterval(timer.current);
          loadBatches();
          onDone?.();
        }
      } catch { clearInterval(timer.current); }
    }, 1500);
  };

  const submit = async () => {
    if (!file) return;
    setError(""); setBusy(true); setBatch(null);
    try {
      const b = await api.upload(file);
      setBatch(b);
      poll(b.id);
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  const running = batch && !["done", "failed"].includes(batch.status);

  return (
    <section>
      <div
        className={`drop ${drag ? "drag" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); setFile(e.dataTransfer.files[0]); }}
      >
        <p>Drag & drop a <b>.csv</b> or <b>.xlsx</b> file containing URLs, or</p>
        <input type="file" accept=".csv,.xlsx,.xlsm,.txt" onChange={(e) => setFile(e.target.files[0])} />
        {file && <p className="muted">Selected: {file.name}</p>}
        <button className="primary" disabled={!file || busy || running} onClick={submit}>
          {busy ? "Uploading…" : "Upload & harvest"}
        </button>
        {error && <p className="error">{error}</p>}
      </div>

      {batch && (
        <div className="card">
          <div className="row">
            <b>{batch.file_name}</b>
            <span className={`pill ${batch.status}`}>{batch.status}</span>
          </div>
          <div className="bar"><div style={{ width: `${batch.progress}%` }} /></div>
          <p className="muted">
            {batch.processed_urls} / {batch.total_urls} URLs harvested
            {batch.status === "indexing" && " · building embeddings…"}
          </p>
          {batch.error && <p className="error">{batch.error}</p>}
          {batch.status === "done" && <button onClick={goToUrls}>View harvested URLs →</button>}
        </div>
      )}

      <h3>Previous uploads</h3>
      <table>
        <thead><tr><th>File</th><th>Status</th><th>URLs</th><th>Uploaded</th></tr></thead>
        <tbody>
          {batches.map((b) => (
            <tr key={b.id}>
              <td>{b.file_name}</td>
              <td><span className={`pill ${b.status}`}>{b.status}</span></td>
              <td>{b.processed_urls}/{b.total_urls}</td>
              <td>{new Date(b.created_at).toLocaleString()}</td>
            </tr>
          ))}
          {!batches.length && <tr><td colSpan="4" className="muted">No uploads yet.</td></tr>}
        </tbody>
      </table>
    </section>
  );
}
