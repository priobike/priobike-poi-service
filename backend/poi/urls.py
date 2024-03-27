from django.urls import path

from . import views

app_name = "poi"

urlpatterns = [
    path(
        "match/", views.MatchConstructionResource.as_view(), name="match-construction"
    ),
]
