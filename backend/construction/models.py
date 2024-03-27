from django.conf import settings
from django.contrib.gis.db import models


class Construction(models.Model):
    """A construction site."""

    # The unique identifier of the construction site.
    name = models.CharField(max_length=255)

    # The coordinate of the construction site.
    coordinate = models.PointField(srid=settings.LONLAT, geography=True)

    def __str__(self) -> str:
        return f"{self.name} at {self.coordinate}"

    class Meta:
        verbose_name = "Construction"
        verbose_name_plural = "Constructions"
