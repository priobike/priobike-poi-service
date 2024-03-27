from django.conf import settings
from django.contrib.gis.db import models
from django.utils import timezone


class Construction(models.Model):
    """A construction site."""

    # The coordinate of the construction site.
    coordinate = models.PointField(srid=settings.LONLAT, geography=True)

    # The date the contruction site was created.
    date = models.DateTimeField(default=timezone.now)

    # The type of contruction site.
    category = models.CharField(max_length=255)

    def __str__(self) -> str:
        return f"{self.category} at {self.coordinate}"

    class Meta:
        verbose_name = "Construction"
        verbose_name_plural = "Construction"


class Recommendation(models.Model):
    """A spot with good bike riding conditions."""

    # The coordinate of the recommendation.
    coordinate = models.PointField(srid=settings.LONLAT, geography=True)

    # The date the recommendation was created.
    date = models.DateTimeField(default=timezone.now)

    # The type of recommendation.
    category = models.CharField(max_length=255)

    def __str__(self) -> str:
        return f"{self.category} at {self.coordinate}"

    class Meta:
        verbose_name = "Recommendation"
        verbose_name_plural = "Recommendations"


class ConstructionSpot(models.Model):
    """A construction spot (a clustered collection of construction)."""

    # The coordinate of the contruction site.
    coordinate = models.PointField(srid=settings.LONLAT, geography=True)

    # The valuation of the contruction site (positive if more contruction sites are present, negative if more recommendations are present).
    value = models.IntegerField(default=0)

    # The polygon of the convex hull contruction site.
    border = models.PolygonField(srid=settings.LONLAT, geography=True, null=True)
