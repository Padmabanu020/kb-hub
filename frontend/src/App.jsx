import { useEffect, useState } from "react";
import { api } from "./api";
import Upload from "./components/Upload.jsx";
import UrlTable from "./components/UrlTable.jsx";
import Search from "./components/Search.jsx";

const TABS = [
  ["search", "Search"],
  ["upload", "Upload CSV"],
  ["urls", "Harvested URLs"],
];

export default function App() {
  const [tab, setTab] = useState("search");
  const [stats, setStats] = useState(null);

  const refreshStats = () => api.stats().then(setStats).catch(() => setStats(null));
  useEffect(() => { refreshStats(); }, [tab]);

  return (
    <div className="app">
      <header>
        <h1>📚 Knowledge Base Hub</h1>
        {stats && (
          <div className="stats">
            <span><b>{stats.urls}</b> URLs</span>
            <span><b>{stats.indexed_urls}</b> indexed</span>
            <span><b>{stats.vectors}</b> vectors</span>
          </div>
        )}
      </header>
      <nav>
        {TABS.map(([id, label]) => (
          <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>
        ))}
      </nav>
      <main>
        {tab === "search" && <Search stats={stats} />}
        {tab === "upload" && <Upload onDone={refreshStats} goToUrls={() => setTab("urls")} />}
        {tab === "urls" && <UrlTable />}
      </main>
    </div>
  );
}
