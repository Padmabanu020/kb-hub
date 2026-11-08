import os
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from pathlib import Path

from . import vectorstore
from .chunker import chunk_text
from .models import HarvestedURL
from .scraper import parse_html
from .views import extract_urls

HTML = """<html><head><title>Leadership | Acme</title><meta name="description" content="Acme leaders"></head>
<body><nav>menu</nav><h1>Our Leadership</h1><h2>Executive Team</h2>
<div class="card"><div>Jane Doe</div><div>Chief Executive Officer</div></div>
<p>Jane Doe, Chief Executive Officer, joined Acme in 2015 and previously led product at Globex.</p>
<p>John Smith - Chief Financial Officer. John oversees finance and investor relations at Acme.</p>
<h2>Products</h2><p>Acme builds rockets, anvils and other widgets for industrial customers worldwide.</p>
</body></html>"""

FAKE = {"final_url": "https://acme.test/team", "http_status": 200, "content_type": "text/html",
        "raw": HTML, "error": "", **dict(zip(("title", "text", "metadata"), parse_html(HTML)))}


class HubTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ov = override_settings(EMBEDDING_MODEL="hash", FAISS_DIR=Path(self.tmp), LLM_ENABLED=False)
        self.ov.enable()
        vectorstore.reset_singletons()
        import hub.embeddings as e
        e._embedder = None

    def tearDown(self):
        self.ov.disable()

    def test_extract_urls(self):
        rows = [["Name", "Website"], ["A", "https://a.com"], ["B", "www.b.org"], ["C", "nope"], ["D", "https://a.com"]]
        self.assertEqual(extract_urls(rows), ["https://a.com", "https://www.b.org"])

    def test_chunking_keeps_context(self):
        _, text, _ = parse_html(HTML)
        chunks = chunk_text("Acme", text, 300)
        self.assertTrue(any("Chief Executive Officer" in c for c in chunks))
        self.assertTrue(all(c.startswith("Acme") for c in chunks))

    def test_end_to_end(self):
        csv_file = SimpleUploadedFile("urls.csv", b"url\nhttps://acme.test/team\n", content_type="text/csv")
        with mock.patch("hub.pipeline.fetch_url", return_value=FAKE):
            r = self.client.post("/api/upload/?sync=1", {"file": csv_file})
        self.assertEqual(r.status_code, 202)
        row = HarvestedURL.objects.get()
        self.assertEqual(row.http_status, 200)
        self.assertTrue(row.indexed and row.chunk_count > 0)

        api = self.client.get("/api/urls/").json()
        self.assertEqual(api["count"], 1)
        self.assertIn("raw_content", api["results"][0])
        self.assertNotIn("raw_content", self.client.get("/api/urls/?light=1").json()["results"][0])

        s = self.client.post("/api/search/", {"query": "Who is the chief executive officer?"},
                             content_type="application/json").json()
        self.assertTrue(s["passages"])
        self.assertTrue(any("Jane Doe" in p["name"] for p in s["people"]))
        self.assertEqual(self.client.get("/api/stats/").json()["vectors"], row.chunk_count)
        self.assertGreater(self.client.post("/api/reindex/").json()["chunks_indexed"], 0)
