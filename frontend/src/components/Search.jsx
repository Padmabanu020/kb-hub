import { useState } from "react";
import { api } from "../api";

const EXAMPLES = [
  "Who is the CEO?",
  "Show the leadership team and their roles",
  "Biography of the founder",
];

export default function Search({ stats }) {
  const [query, setQuery] = useState("");
  const [useLlm, setUseLlm] = useState(true);
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState(null);
  const [error, setError] = useState("");

  const run = async (text = query) => {
    if (!text.trim()) return;
    setQuery(text);
    setLoading(true);
    setError("");
    try {
      setRes(await api.search(text, 8, useLlm));
    } catch (e) {
      setError(e.message);
      setRes(null);
    }
    setLoading(false);
  };

  return (
    <section>
      <form
        className="searchbar"
        onSubmit={(e) => {
          e.preventDefault();
          run();
        }}
      >
        <input
          autoFocus
          placeholder="Ask about people, roles, biographies…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="primary" disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>
      <div className="row">
        {EXAMPLES.map((x) => (
          <button key={x} className="chip" onClick={() => run(x)}>
            {x}
          </button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}

      {res && (
        <>
          <div className="card answer">
            <div className="row">
              <b>Answer</b>
              <span className={`pill ${res.mode}`}>
                {res.mode === "llm" ? "LLM" : "heuristic"}
              </span>
            </div>
            <p>{res.answer || "No answer."}</p>
            {res.llm_error && (
              <p className="muted">
                LLM unavailable, used fallback ({res.llm_error}).
              </p>
            )}
          </div>

          {res.people.length > 0 && (
            <>
              <h3>People</h3>
              <div className="grid">
                {res.people.map((p, i) => (
                  <div className="card person" key={i}>
                    <div className="avatar">
                      {p.name
                        .split(" ")
                        .map((w) => w[0])
                        .slice(0, 2)
                        .join("")}
                    </div>
                    <div>
                      <h4>{p.name}</h4>
                      <div className="role">{p.role || "—"}</div>
                      {p.bio && <p>{p.bio}</p>}
                      {p.source_url && (
                        <a href={p.source_url} target="_blank" rel="noreferrer">
                          Source ↗
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          <h3>Relevant passages ({res.passages.length})</h3>
          {res.passages.map((p) => (
            <details key={p.chunk_id} className="card passage">
              <summary>
                <span className="score">{p.score.toFixed(2)}</span>{" "}
                {p.title || p.url}
              </summary>
              <pre>{p.text}</pre>
              <a href={p.url} target="_blank" rel="noreferrer">
                {p.url}
              </a>
            </details>
          ))}
          {!res.passages.length && (
            <p className="muted">Nothing indexed yet. Upload a CSV first.</p>
          )}
        </>
      )}
    </section>
  );
}
