import requests
from construction.models import Construction
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand


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

class Command(BaseCommand):
    help = """
    Import Construction Sites for a given area.
    """

    def add_arguments(self, parser):
        parser.add_argument("area", type=str, help="The area to fetch construction data for")

    def handle(self, *args, **options):
        """
        Fetch construction data from overpass turbo.
        """

        # Parse the area argument from the command line args
        area = options["area"]
        assert area, "Area is required"

        print("Clearing database")

        try:
            Construction.objects.all().delete()
        except Exception as e:
            print("Failed to delete existing construction sites: " + str(e))
            return

        print("Importing construction data from overpass turbo")

        BASE_URL = "overpass-api.de"
        API = "https://" + BASE_URL + "/api/interpreter"
        DATA = query(area)

        try:
            response = requests.post(API, data=DATA)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print("Failed to fetch construction data: " + str(e))
            return
        
        types = set()
        elements_by_id = {element["id"]: element for element in data["elements"]}
        construction_sites = []
        for element in data["elements"]:
            if element["type"] == "node":
                c = Construction(coordinate=Point(element["lon"], element["lat"], srid=4326))
                construction_sites.append(c)
            elif element["type"] == "way":
                for node in element["nodes"]:
                    node_data = elements_by_id[node]
                    c = Construction(coordinate=Point(node_data["lon"], node_data["lat"], srid=4326))
                    construction_sites.append(c)

        Construction.objects.bulk_create(construction_sites)
        print(f"Imported {len(construction_sites)} construction sites")
