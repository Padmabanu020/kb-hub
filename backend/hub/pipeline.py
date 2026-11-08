"""Upload -> scrape -> SQL storage -> chunk -> embed -> FAISS."""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.conf import settings
from django.db import connection
from django.utils import timezone

from .chunker import chunk_text, person_chunks
from .embeddings import get_embedder
from .models import Chunk, HarvestedURL, UploadBatch
from .scraper import fetch_url
from .vectorstore import get_store


def apply_result(row, res):
    row.final_url = res["final_url"]
    row.http_status = res["http_status"]
    row.content_type = res["content_type"]
    row.title = res["title"]
    row.raw_content = res["raw"]
    row.text_content = res["text"]
    row.metadata = res["metadata"]
    row.error = res["error"]
    row.fetched_at = timezone.now()
    row.indexed = False
    row.chunk_count = 0
    row.save()


def index_url(row):
    """(Re)build chunks + embeddings for one harvested URL."""
    store = get_store()
    old = list(row.chunks.values_list("id", flat=True))
    if old:
        store.remove(old)
        row.chunks.all().delete()
    if not (row.http_status and 200 <= row.http_status < 300 and row.text_content):
        row.indexed, row.chunk_count = False, 0
        row.save(update_fields=["indexed", "chunk_count"])
        return 0
    texts = person_chunks(row.title, row.metadata.get("persons_json_ld")) + \
        chunk_text(row.title, row.text_content, settings.CHUNK_SIZE)
    Chunk.objects.bulk_create([Chunk(url=row, position=i, text=t) for i, t in enumerate(texts)])
    chunks = list(row.chunks.order_by("position"))  # re-read to get pks on every backend
    vectors = get_embedder().encode([c.text for c in chunks])
    store.add([c.id for c in chunks], vectors)
    row.indexed, row.chunk_count = True, len(chunks)
    row.save(update_fields=["indexed", "chunk_count"])
    return len(chunks)


def run_batch(batch_id):
    try:
        batch = UploadBatch.objects.get(pk=batch_id)
        batch.status = "scraping"
        batch.save(update_fields=["status"])
        rows = list(batch.urls.filter(fetched_at__isnull=True))
        with ThreadPoolExecutor(max_workers=settings.SCRAPE_WORKERS) as pool:
            futures = {pool.submit(fetch_url, r.url): r for r in rows}
            for fut in as_completed(futures):
                apply_result(futures[fut], fut.result())
                batch.processed_urls += 1
                batch.save(update_fields=["processed_urls"])
        batch.status = "indexing"
        batch.save(update_fields=["status"])
        for row in batch.urls.filter(http_status__gte=200, http_status__lt=300):
            index_url(row)
        batch.status = "done"
        batch.save(update_fields=["status"])
    except Exception as exc:
        UploadBatch.objects.filter(pk=batch_id).update(status="failed", error=str(exc)[:2000])
    finally:
        connection.close()


def start_batch(batch_id, background=True):
    if not background:
        return run_batch(batch_id)
    threading.Thread(target=run_batch, args=(batch_id,), daemon=True).start()


def reindex_all():
    """Drop the FAISS index and rebuild it from the SQL database."""
    get_store().reset()
    total = 0
    for row in HarvestedURL.objects.filter(http_status__gte=200, http_status__lt=300):
        row.chunks.all().delete()
        total += index_url(row)
    return total
