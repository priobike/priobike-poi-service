import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from pois.models import Poi


def import_from_mapdata_service(base_url):
    print("Importing green wave data from priobike-map-data")

    API = f"https://{base_url}/map-data/static_green_waves_v2.geojson"
    print(f"Fetching green waves from {API}")

    try:
        response = requests.get(API)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("Failed to fetch green wave data: " + str(e))
        return

    print(f"Loaded {len(data['features'])} green waves.")

    green_waves = []

    for feature in data["features"]:
        try:
            green_wave = Poi(
                coordinate=Point(
                    feature["geometry"]["coordinates"][0],
                    feature["geometry"]["coordinates"][1],
                    srid=4326,
                ),
                category="greenwave",
            )
            green_waves.append(green_wave)
        except Exception as e:
            print("Failed to create green wave: " + str(e))

    print(f"{len(green_waves)} green waves successfully created.")

    Poi.objects.bulk_create(green_waves)
    print(f"Imported {len(green_waves)} green waves")


class Command(BaseCommand):
    help = """
    Import green waves for a given area.
    """

    def add_arguments(self, parser):
        parser.add_argument("area", type=str, help="The area to fetch green wave data for")

    def handle(self, *args, **options):
        """
        Fetch green wave data from priobike-map-data.
        """

        # Parse the area argument from the command line args
        area = options["area"]
        assert area, "Area is required"

        print("Clearing database")

        try:
            Poi.objects.filter(category="greenwave").delete()
        except Exception as e:
            print("Failed to delete existing green waves: " + str(e))
            return
        
        if area == "Dresden":
            import_from_mapdata_service("priobike.vkw.tu-dresden.de/staging")
        elif area == "Hamburg":
            import_from_mapdata_service("priobike.vkw.tu-dresden.de/production")
        else:
            raise ValueError(f"Unknown area: {area}")

        