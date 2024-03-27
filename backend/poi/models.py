from django.conf import settings
from django.contrib.gis.db import models
from django.utils import timezone


class Construction(models.Model):
    """A construction site."""

    # The unique identifier of the construction site.
    construction_id = models.CharField(max_length=255)

    # The coordinate of the construction site.
    coordinate = models.PointField(srid=settings.LONLAT, geography=True)

    # The date the contruction site was created.
    start_date = models.DateTimeField(default=timezone.now)

    # The date the contruction site will end.
    end_date = models.DateTimeField(null=True, blank=True)

    # The type of contruction site.
    category = models.CharField(max_length=255)

    def __str__(self) -> str:
        return f"{self.category} at {self.coordinate}"

    class Meta:
        verbose_name = "Construction"
        verbose_name_plural = "Construction"
