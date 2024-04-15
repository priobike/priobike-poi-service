from django.conf import settings
from django.contrib.gis.db import models


class Poi(models.Model):
    """A point of interest."""

    # The kind of point of interest.
    category = models.TextField()

    # The coordinate of the point of interest.
    coordinate = models.PointField(srid=settings.LONLAT, geography=True)

    def __str__(self) -> str:
        return f"{self.category} at {self.coordinate}"

    class Meta:
        verbose_name = "Point of interest"
        verbose_name_plural = "Points of interest"


class PoiLine(models.Model):
    """A line of points of interest."""

    # The kind of line of points of interest.
    category = models.TextField()

    # The line of points of interest.
    line = models.LineStringField(srid=settings.LONLAT, geography=True)

    def __str__(self) -> str:
        return f"{self.category} along {self.line}"

    class Meta:
        verbose_name = "Line of points of interest"
        verbose_name_plural = "Lines of points of interest"