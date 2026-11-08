from rest_framework import serializers

from .models import HarvestedURL, UploadBatch


class HarvestedURLSerializer(serializers.ModelSerializer):
    """GET /api/urls/ payload. Pass ?light=1 to omit the (large) raw_content field."""
    batch_file = serializers.CharField(source="batch.file_name", read_only=True)

    class Meta:
        model = HarvestedURL
        fields = ["id", "batch", "batch_file", "url", "final_url", "http_status", "content_type",
                  "title", "raw_content", "metadata", "error", "fetched_at", "indexed", "chunk_count"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        req = self.context.get("request")
        if req is not None and req.query_params.get("light", "").lower() in {"1", "true", "yes"}:
            data.pop("raw_content", None)
        return data


class BatchSerializer(serializers.ModelSerializer):
    progress = serializers.SerializerMethodField()

    class Meta:
        model = UploadBatch
        fields = ["id", "file_name", "created_at", "status", "total_urls", "processed_urls", "progress", "error"]

    def get_progress(self, obj):
        return round(100 * obj.processed_urls / obj.total_urls) if obj.total_urls else 0
