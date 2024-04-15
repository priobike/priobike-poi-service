import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from pois.models import Poi, PoiLine


def import_from_mapdata_service(base_url):
    print("Importing accident hotspot data from priobike-map-data")

    API = f"https://{base_url}/map-data/accident_hot_spots.geojson"
    print(f"Fetching accident hotspots from {API}")

    try:
        response = requests.get(API)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("Failed to fetch accident hotspot data: " + str(e))
        return

    print(f"Loaded {len(data['features'])} accident hotspots.")

    accident_hotspots = []

    for feature in data["features"]:
        try:
            accident_hotspot = Poi(
                coordinate=Point(
                    feature["geometry"]["coordinates"][0],
                    feature["geometry"]["coordinates"][1],
                    srid=4326,
                ),
                category="accidenthotspot",
            )
            accident_hotspots.append(accident_hotspot)
        except Exception as e:
            print("Failed to create accident hotspot: " + str(e))

    print(f"{len(accident_hotspots)} accident hotspots successfully created.")

    Poi.objects.bulk_create(accident_hotspots)
    print(f"Imported {len(accident_hotspots)} accident hotspots")


class Command(BaseCommand):
    help = """
    Import accident hotspots for a given area.
    """

    def add_arguments(self, parser):
        parser.add_argument("area", type=str, help="The area to fetch accident hotspot data for")

    def handle(self, *args, **options):
        """
        Fetch accident hotspot data from priobike-map-data.
        """

        # Parse the area argument from the command line args
        area = options["area"]
        assert area, "Area is required"

        print("Clearing database")

        try:
            Poi.objects.filter(category="accidenthotspot").delete()
            # Not used right now, but to make sure for future editations of the code
            PoiLine.objects.filter(category="accidenthotspot").delete()
        except Exception as e:
            print("Failed to delete existing accident hotspots: " + str(e))
            return
        
        if area == "Dresden":
            import_from_mapdata_service("priobike.vkw.tu-dresden.de/staging")
        elif area == "Hamburg":
            import_from_mapdata_service("priobike.vkw.tu-dresden.de/production")
        else:
            raise ValueError(f"Unknown area: {area}")

        