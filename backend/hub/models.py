from django.db import models


class UploadBatch(models.Model):
    """One uploaded CSV/XLSX file."""
    STATUS = [("pending", "Pending"), ("scraping", "Scraping"), ("indexing", "Indexing"),
              ("done", "Done"), ("failed", "Failed")]
    file_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    total_urls = models.IntegerField(default=0)
    processed_urls = models.IntegerField(default=0)
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.file_name} ({self.status})"


class HarvestedURL(models.Model):
    """Raw scraped content for one URL (relational source of truth)."""
    batch = models.ForeignKey(UploadBatch, on_delete=models.CASCADE, related_name="urls")
    url = models.CharField(max_length=2000)
    final_url = models.CharField(max_length=2000, blank=True, default="")
    http_status = models.IntegerField(null=True, blank=True)
    content_type = models.CharField(max_length=200, blank=True, default="")
    title = models.CharField(max_length=500, blank=True, default="")
    raw_content = models.TextField(blank=True, default="")    # raw HTML
    text_content = models.TextField(blank=True, default="")   # cleaned, structured text
    metadata = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default="")
    fetched_at = models.DateTimeField(null=True, blank=True)  # null => not harvested yet
    indexed = models.BooleanField(default=False)
    chunk_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.url


class Chunk(models.Model):
    """A text chunk; its primary key is the id stored in the FAISS index."""
    url = models.ForeignKey(HarvestedURL, on_delete=models.CASCADE, related_name="chunks")
    position = models.IntegerField(default=0)
    text = models.TextField()

    class Meta:
        ordering = ["url_id", "position"]
