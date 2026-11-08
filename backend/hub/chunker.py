"""Heading-aware chunking: each chunk keeps its page title + section heading as context."""


def chunk_text(title, text, size=900):
    chunks, head, buf, length = [], "", [], 0

    def label():
        parts = [p for p in (title, head) if p]
        return " | ".join(parts)

    def flush(carry):
        nonlocal buf, length
        if not buf:
            return
        body = "\n".join(buf)
        chunks.append((label() + "\n" + body).strip())
        buf = buf[-1:] if carry else []
        length = sum(len(x) for x in buf)

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("# "):
            flush(carry=False)
            head = line[2:].strip()
            continue
        if length + len(line) > size and buf:
            flush(carry=True)
        while len(line) > size * 1.5:  # very long paragraph
            buf.append(line[:size]); length += size
            flush(carry=False)
            line = line[size:]
        buf.append(line)
        length += len(line)
    flush(carry=False)
    return [c for c in chunks if len(c) > 30]


def person_chunks(title, persons):
    out = []
    for p in persons or []:
        bits = [f"Person: {p.get('name')}"]
        if p.get("jobTitle"):
            bits.append(f"Role: {p['jobTitle']}")
        if p.get("worksFor"):
            bits.append(f"Organization: {p['worksFor']}")
        if p.get("description"):
            bits.append(f"Bio: {p['description']}")
        out.append((title + "\n" if title else "") + "\n".join(bits))
    return out
