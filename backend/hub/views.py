import csv
import io
import re

from django.conf import settings
from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Chunk, HarvestedURL, UploadBatch
from .pipeline import reindex_all, start_batch
from .retrieval import semantic_search
from .llm import extract_structured
from .serializers import BatchSerializer, HarvestedURLSerializer
from .vectorstore import get_store

DOMAIN_RE = re.compile(r"^(?:[\w-]+\.)+[a-z]{2,}(?:[/:?#]\S*)?$", re.I)
URL_COLUMN_HINTS = ("url", "link", "website", "site", "web")


def normalize_url(value):
    s = str(value or "").strip()
    if not s:
        return None
    if re.match(r"^https?://", s, re.I):
        return s
    if s.lower().startswith("www.") or DOMAIN_RE.match(s):
        return "https://" + s
    return None


def extract_urls(rows):
    """rows: list of lists. Uses a header column named url/link/website if present, otherwise scans all cells."""
    if not rows:
        return []
    header = [str(c or "").strip().lower() for c in rows[0]]
    col = next((i for i, h in enumerate(header) if any(k in h for k in URL_COLUMN_HINTS)), None)
    body = rows[1:] if col is not None else rows
    urls = []
    for r in body:
        cells = [r[col]] if col is not None and col < len(r) else r
        for c in cells:
            u = normalize_url(c)
            if u:
                urls.append(u)
    return list(dict.fromkeys(urls))


def read_rows(upload):
    name = upload.name.lower()
    data = upload.read()
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), data_only=True)
        rows = []
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                rows.append([(c.hyperlink.target if c.hyperlink and c.hyperlink.target else c.value) for c in row])
        return rows
    text = data.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


class UploadView(APIView):
    """POST /api/upload/  (multipart, field name 'file'; .csv or .xlsx)"""
    parser_classes = [MultiPartParser]

    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response({"error": "No file uploaded (use form field 'file')."}, status=400)
        if not f.name.lower().endswith((".csv", ".xlsx", ".xlsm", ".txt")):
            return Response({"error": "Please upload a .csv or .xlsx file."}, status=400)
        try:
            urls = extract_urls(read_rows(f))
        except Exception as exc:
            return Response({"error": f"Could not parse file: {exc}"}, status=400)
        if not urls:
            return Response({"error": "No URLs found in the file."}, status=400)
        batch = UploadBatch.objects.create(file_name=f.name[:255], total_urls=len(urls))
        HarvestedURL.objects.bulk_create([HarvestedURL(batch=batch, url=u[:2000]) for u in urls])
        start_batch(batch.id, background=not request.query_params.get("sync"))
        batch.refresh_from_db()
        return Response(BatchSerializer(batch).data, status=status.HTTP_202_ACCEPTED)


class BatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UploadBatch.objects.all()
    serializer_class = BatchSerializer


class HarvestedURLViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/urls/ and /api/urls/<id>/
    Filters: ?batch=<id>  ?http_status=200  ?indexed=true  ?q=<text in url/title>  ?light=1"""
    serializer_class = HarvestedURLSerializer

    def get_queryset(self):
        qs = HarvestedURL.objects.select_related("batch").order_by("-id")
        p = self.request.query_params
        if p.get("batch"):
            qs = qs.filter(batch_id=p["batch"])
        if p.get("http_status"):
            qs = qs.filter(http_status=p["http_status"])
        if p.get("indexed"):
            qs = qs.filter(indexed=p["indexed"].lower() in {"1", "true", "yes"})
        if p.get("q"):
            qs = qs.filter(Q(url__icontains=p["q"]) | Q(title__icontains=p["q"]))
        return qs


class SearchView(APIView):
    """POST /api/search/  {"query": "...", "top_k": 8, "use_llm": true}"""

    def post(self, request):
        query = (request.data.get("query") or "").strip()
        if not query:
            return Response({"error": "query is required"}, status=400)
        try:
            top_k = max(1, min(int(request.data.get("top_k", 8)), 25))
        except (TypeError, ValueError):
            top_k = 8
        use_llm = request.data.get("use_llm", True) not in (False, "false", "0", 0)
        hits = semantic_search(query, top_k)
        result, mode = extract_structured(query, hits, use_llm)
        sources = list(dict.fromkeys(h["url"] for h in hits))
        return Response({"query": query, "mode": mode, "answer": result.get("answer", ""),
                         "people": result.get("people", []), "llm_error": result.get("llm_error"),
                         "sources": sources, "passages": hits})


@api_view(["POST"])
def reindex(request):
    n = reindex_all()
    return Response({"chunks_indexed": n})


@api_view(["GET"])
def stats(request):
    by_status = HarvestedURL.objects.values("http_status").annotate(n=Count("id")).order_by("-n")
    return Response({
        "urls": HarvestedURL.objects.count(),
        "indexed_urls": HarvestedURL.objects.filter(indexed=True).count(),
        "chunks": Chunk.objects.count(),
        "vectors": get_store().count,
        "by_status": list(by_status),
        "embedding_model": settings.EMBEDDING_MODEL,
        "llm": {"enabled": settings.LLM_ENABLED, "model": settings.LLM_MODEL, "base_url": settings.LLM_BASE_URL},
    })
