import requests
from django.contrib.gis.geos import LineString, Point
from django.core.management.base import BaseCommand
from pois.models import Poi, PoiLine

def import_from_mapdata_service(area):
    print("Importing construction sites data from priobike-map-data")
    
    if area == "Dresden":
        base_url = "priobike.vkw.tu-dresden.de/staging"
    elif area == "Hamburg":
        base_url = "priobike.vkw.tu-dresden.de/production"
    else:
        raise ValueError(f"Unknown area: {area}")

    API = f"https://{base_url}/map-data/construction_sites_v2.geojson"
    print(f"Fetching construction sites from {API}")

    try:
        response = requests.get(API)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("Failed to fetch construction sites data: " + str(e))
        return

    print(f"Loaded {len(data['features'])} construction sites.")

    construction_sites = []

    for feature in data["features"]:
        try:
            construction_site = Poi(
                coordinate=Point(
                    feature["geometry"]["coordinates"][0],
                    feature["geometry"]["coordinates"][1],
                    srid=4326,
                ),
                category="construction",
            )
            construction_sites.append(construction_site)
        except Exception as e:
            print("Failed to create construction site: " + str(e))

    print(f"{len(construction_sites)} construction successfully created.")

    Poi.objects.bulk_create(construction_sites)
    print(f"Imported {len(construction_sites)} construction sites")

def import_from_overpass(area):
    def query(area):
        return f"""
            [out:json][timeout:25];

            // Define the area of Dresden
            area["name"="{area}"]->.a;

            // Search for nodes and ways with the "construction" tag within the defined area
            (
            node["construction"](area.a);
            way["construction"](area.a);
            );

            // Output data
            out body;
            >;
            out skel qt;
        """
        
    print("Importing construction data from overpass turbo")

    BASE_URL = "overpass-api.de"
    API = "https://" + BASE_URL + "/api/interpreter"
    print(f"Fetching construction sites from {API}")
    DATA = query(area)

    try:
        response = requests.post(API, data=DATA)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("Failed to fetch construction data: " + str(e))
        return
    
    elements_by_id = {element["id"]: element for element in data["elements"]}
    construction_sites_points = []
    construction_sites_lines = []
    for element in data["elements"]:
        if element["type"] == "node":
            # Make a point
            c = Poi(coordinate=Point(element["lon"], element["lat"], srid=4326), category="construction")
            construction_sites_points.append(c)
        elif element["type"] == "way":
            # Make a linestring
            line = LineString([
                Point(elements_by_id[node]["lon"], elements_by_id[node]["lat"], srid=4326) 
                for node in element["nodes"]
            ])
            start = Point(elements_by_id[element["nodes"][0]]["lon"], elements_by_id[element["nodes"][0]]["lat"], srid=4326)
            end = Point(elements_by_id[element["nodes"][-1]]["lon"], elements_by_id[element["nodes"][-1]]["lat"], srid=4326)
            c = PoiLine(line=line, start=start, end=end, category="construction")
            construction_sites_lines.append(c)

    Poi.objects.bulk_create(construction_sites_points)
    PoiLine.objects.bulk_create(construction_sites_lines)
    print(f"Imported {len(construction_sites_points) + len(construction_sites_lines)} construction sites")

class Command(BaseCommand):
    help = """
    Import Construction Sites for a given area.
    """

    def add_arguments(self, parser):
        parser.add_argument("area", type=str, help="The area to fetch construction data for")

    def handle(self, *args, **options):
        """
        Fetch construction data.
        """

        # Parse the area argument from the command line args
        area = options["area"]
        assert area, "Area is required"

        print("Clearing database")

        try:
            Poi.objects.filter(category="construction").delete()
            PoiLine.objects.filter(category="construction").delete()
        except Exception as e:
            print("Failed to delete existing construction sites: " + str(e))
            return

        print("Importing construction data")
        
        import_from_overpass(area)
        import_from_mapdata_service(area)