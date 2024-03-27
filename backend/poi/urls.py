from django.urls import path

from . import views

app_name = "poi"

urlpatterns = [
    path("post/", views.PostConstructionResource.as_view(), name="send-construction"),
    path(
        "match/", views.MatchConstructionResource.as_view(), name="match-construction"
    ),
]
