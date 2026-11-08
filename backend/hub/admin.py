from django.contrib import admin
from .models import Chunk, HarvestedURL, UploadBatch

admin.site.register(UploadBatch)
admin.site.register(Chunk)


@admin.register(HarvestedURL)
class HarvestedURLAdmin(admin.ModelAdmin):
    list_display = ("url", "http_status", "title", "indexed", "chunk_count")
    list_filter = ("http_status", "indexed")
    search_fields = ("url", "title")
    exclude = ("raw_content",)
