from django.urls import path

from . import views

urlpatterns = [
    path("", views.index),
    path("new/", views.create),
    path("list/", views.PostList.as_view()),
    path("<int:pk>/", views.PostDetail.as_view()),
]
