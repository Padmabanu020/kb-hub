import json
import re

import requests
from django.conf import settings

SYSTEM = (
    "You extract person-related information from website excerpts. Use ONLY the excerpts. "
    "Never invent facts. Reply with a single JSON object: "
    '{"answer": "<2-4 sentence answer to the question>", '
    '"people": [{"name": "", "role": "", "bio": "", "source_url": ""}]}. '
    "Include every relevant person found; leave a field empty if unknown."
)
ROLE_WORDS = (r"(?:chief [a-z ]+officer|ceo|cfo|cto|coo|cio|ciso|president|vice president|vp[, ]|"
              r"founder|co-founder|chair(?:man|woman|person)?|managing director|director|partner|"
              r"head of [a-z ]+|general manager|principal)")
NAME = r"([A-Z][a-zA-Z.'\-]+(?: [A-Z][a-zA-Z.'\-]+){1,3})"
BAD_FIRST = {"assistant", "executive", "senior", "associate", "vice", "chief", "head", "office", "contact",
             "about", "our", "the", "meet", "board", "managing", "general", "deputy", "acting", "former"}


def llm_available():
    return settings.LLM_ENABLED


def _context(hits, limit=6000):
    parts, used = [], 0
    for i, h in enumerate(hits, 1):
        block = f"[{i}] URL: {h['url']}\n{h['text']}"
        if used + len(block) > limit:
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)


def _parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON in LLM reply")
    return json.loads(m.group(0))


def llm_extract(query, hits):
    r = requests.post(
        settings.LLM_BASE_URL.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
        json={"model": settings.LLM_MODEL, "temperature": 0.1,
              "messages": [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": f"Question: {query}\n\nExcerpts:\n{_context(hits)}"}]},
        timeout=settings.LLM_TIMEOUT)
    r.raise_for_status()
    data = _parse_json(r.json()["choices"][0]["message"]["content"])
    people = [p for p in data.get("people", []) if isinstance(p, dict) and p.get("name")]
    return {"answer": str(data.get("answer", "")), "people": people}


def heuristic_extract(query, hits):
    """Regex fallback: 'Jane Doe, Chief Executive Officer' / 'Jane Doe - CEO' / 'Role: Jane Doe'."""
    people, seen = [], set()
    pat1 = re.compile(NAME + r"\s*[,\-\u2013|:(]\s*(" + ROLE_WORDS + r"[^\n.;|]{0,60})", re.I)
    pat2 = re.compile(r"(" + ROLE_WORDS + r"[^\n:]{0,40})\s*[:\-\u2013]\s*" + NAME, re.I)
    for h in hits:
        for line in h["text"].split("\n"):
            found = [(m.group(1), m.group(2)) for m in pat1.finditer(line)] + \
                    [(m.group(2), m.group(1)) for m in pat2.finditer(line)]
            for name, role in found:
                key = name.lower()
                words = key.split()
                if key in seen or len(words) < 2 or words[0] in BAD_FIRST \
                        or any(w in {"to", "of", "and", "at", "for"} for w in words):
                    continue
                seen.add(key)
                bio = next((l for l in h["text"].split("\n") if name in l and len(l) > len(name) + len(role) + 40), "")
                people.append({"name": name.strip(), "role": role.strip(" ,.-"), "bio": bio[:400],
                               "source_url": h["url"]})
    if h := (hits[0] if hits else None):
        answer = f"Top match: {h['title'] or h['url']}."
        if people:
            answer = f"Found {len(people)} relevant {'person' if len(people)==1 else 'people'} in the harvested pages."
    else:
        answer = "No relevant content found."
    return {"answer": answer, "people": people[:15]}


def extract_structured(query, hits, use_llm=True):
    """Returns (result_dict, mode) where mode is 'llm' | 'heuristic'."""
    if use_llm and llm_available() and hits:
        try:
            return llm_extract(query, hits), "llm"
        except Exception as exc:
            res = heuristic_extract(query, hits)
            res["llm_error"] = f"{type(exc).__name__}: {exc}"[:300]
            return res, "heuristic"
    return heuristic_extract(query, hits), "heuristic"