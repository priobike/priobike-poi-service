import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from pois.models import Poi


def import_from_mapdata_service(base_url):
    print("Importing velo route data from priobike-map-data")

    API = f"https://{base_url}/map-data/velo_routes_v2.geojson"
    print(f"Fetching velo routes from {API}")

    try:
        response = requests.get(API)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("Failed to fetch velo route data: " + str(e))
        return

    print(f"Loaded {len(data['features'])} velo routes.")

    velo_routes = []

    for feature in data["features"]:
        try:
            velo_route = Poi(
                coordinate=Point(
                    feature["geometry"]["coordinates"][0],
                    feature["geometry"]["coordinates"][1],
                    srid=4326,
                ),
                category="veloroute",
            )
            velo_routes.append(velo_route)
        except Exception as e:
            print("Failed to create velo route: " + str(e))

    print(f"{len(velo_routes)} velo routes successfully created.")

    Poi.objects.bulk_create(velo_routes)
    print(f"Imported {len(velo_routes)} velo routes")


class Command(BaseCommand):
    help = """
    Import velo routes for a given area.
    """

    def add_arguments(self, parser):
        parser.add_argument("area", type=str, help="The area to fetch velo route data for")

    def handle(self, *args, **options):
        """
        Fetch velo route data from priobike-map-data.
        """

        # Parse the area argument from the command line args
        area = options["area"]
        assert area, "Area is required"

        print("Clearing database")

        try:
            Poi.objects.filter(category="veloroute").delete()
        except Exception as e:
            print("Failed to delete existing velo routes: " + str(e))
            return
        
        if area == "Dresden":
            import_from_mapdata_service("priobike.vkw.tu-dresden.de/staging")
        elif area == "Hamburg":
            import_from_mapdata_service("priobike.vkw.tu-dresden.de/production")
        else:
            raise ValueError(f"Unknown area: {area}")

        