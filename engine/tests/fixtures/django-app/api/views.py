from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from blog.models import Author


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        author = Author.objects.get(pk=pk)
        author.save()
