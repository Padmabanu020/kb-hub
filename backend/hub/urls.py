from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("urls", views.HarvestedURLViewSet, basename="urls")
router.register("batches", views.BatchViewSet, basename="batches")

urlpatterns = [
    path("upload/", views.UploadView.as_view()),
    path("search/", views.SearchView.as_view()),
    path("reindex/", views.reindex),
    path("stats/", views.stats),
    path("", include(router.urls)),
]
