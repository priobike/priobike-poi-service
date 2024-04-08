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
