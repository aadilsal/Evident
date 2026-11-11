from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView

from .models import Post


def index(request):
    return list(Post.objects.all())


@login_required
@require_http_methods(["POST"])
def create(request):
    Post.objects.create(title=request.POST["title"], author_id=1)


class PostList(ListView):
    model = Post


class PostDetail(View):
    def get(self, request, pk):
        return get_object_or_404(Post, pk=pk)

    def delete(self, request, pk):
        post = Post.objects.get(pk=pk)
        post.delete()
