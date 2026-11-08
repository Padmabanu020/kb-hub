import os
import re
from urllib.parse import urlparse

from .embeddings import get_embedder
from .models import Chunk, HarvestedURL
from .vectorstore import get_store

ROLE_RE = re.compile(r"\b(ceo|cfo|cto|coo|chief|president|vice president|vp|director|founder|co-founder|"
                     r"chair(man|woman)?|partner|head of|officer|manager|board|executive|leadership|team)\b", re.I)
PERSON_Q = re.compile(r"\b(who|ceo|cfo|cto|founder|executive|leader|director|head|bio|biograph|"
                      r"president|chair|board|team|manager|person|people)\b", re.I)

# Words that never identify a company/site, in queries or in URLs/titles.
GENERIC = {
    "the", "and", "for", "with", "who", "what", "which", "show", "list", "tell", "about", "give", "find",
    "ceo", "cfo", "cto", "coo", "founder", "founders", "chief", "officer", "executive", "executives",
    "leader", "leaders", "leadership", "team", "teams", "management", "board", "director", "directors",
    "president", "people", "person", "role", "roles", "biography", "bio", "company", "corporate", "page",
    "home", "access", "denied", "not", "found", "org", "com", "net", "www", "html", "index", "their",
    "his", "her", "are", "is", "of", "in", "at", "on", "to", "a", "an", "me", "all", "details", "information",
}
MIN_SCORE = float(os.environ.get("MIN_SCORE", "0.25"))


def _words(text):
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower())]


def query_terms(query):
    return [w for w in _words(query) if len(w) >= 4 and w not in GENERIC]


def entity_keys(url, title="", metadata=None):
    """Words that identify the site behind a harvested URL: domain labels, path segments, site name."""
    parsed = urlparse(url)
    host_parts = (parsed.hostname or "").lower().split(".")
    keys = set(host_parts[:-1] if len(host_parts) > 1 else host_parts)
    for seg in parsed.path.split("/"):
        keys.update(_words(seg))
    keys.update(_words(title))
    if metadata:
        keys.update(_words(metadata.get("og:site_name", "")))
    return {k for k in keys if len(k) >= 4 and k not in GENERIC}


def _matches(term, key):
    return term == key or (len(term) >= 5 and len(key) >= 5 and (term in key or key in term))


def scoped_url_ids(query):
    """Harvested URLs the query explicitly names (by site/company), or an empty set."""
    terms = query_terms(query)
    if not terms:
        return set()
    ids = set()
    for row in HarvestedURL.objects.filter(indexed=True).only("id", "url", "title", "metadata"):
        keys = entity_keys(row.url, row.title, row.metadata)
        if any(_matches(t, k) for t in terms for k in keys):
            ids.add(row.id)
    return ids


def semantic_search(query, top_k=8):
    store = get_store()
    if store.count == 0:
        return []
    scoped = scoped_url_ids(query)
    vec = get_embedder().encode([query])
    # When scoped to a named site, look at every vector so none of that site's chunks are missed.
    k = store.count if scoped else max(top_k * 4, 20)
    hits = store.search(vec, k)
    if not hits:
        return []
    chunks = {c.id: c for c in Chunk.objects.filter(id__in=[i for i, _ in hits]).select_related("url")}
    person_query = bool(PERSON_Q.search(query))
    results = []
    for cid, score in hits:
        c = chunks.get(cid)
        if not c:
            continue
        if scoped and c.url_id not in scoped:
            continue
        if not scoped and score < MIN_SCORE:
            continue
        boosted = score + (0.05 if person_query and ROLE_RE.search(c.text) else 0.0)
        results.append({"chunk_id": cid, "score": round(boosted, 4), "text": c.text,
                        "url": c.url.url, "title": c.url.title, "url_id": c.url_id})
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]