from django.urls import path

from . import views

app_name = "pois"

urlpatterns = [
    path("match", views.MatchPoisResource.as_view(), name="match-pois"),
]
