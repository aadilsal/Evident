from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuthorViewSet

router = DefaultRouter()
router.register(r"authors", AuthorViewSet)

urlpatterns = [path("", include(router.urls))]
