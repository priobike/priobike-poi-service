import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from pois.models import Landmark

# def import_from_mapdata_service(area):
#     print("Importing construction sites data from priobike-map-data")

#     if area == "Dresden":
#         base_url = "priobike.vkw.tu-dresden.de/staging"
#     elif area == "Hamburg":
#         base_url = "priobike.vkw.tu-dresden.de/production"
#     else:
#         raise ValueError(f"Unknown area: {area}")

#     API = f"https://{base_url}/map-data/construction_sites_v2.geojson"
#     print(f"Fetching construction sites from {API}")

#     try:
#         response = requests.get(API)
#         response.raise_for_status()
#         data = response.json()
#     except Exception as e:
#         print("Failed to fetch construction sites data: " + str(e))
#         return

#     print(f"Loaded {len(data['features'])} construction sites.")

#     construction_sites = []

#     for feature in data["features"]:
#         try:
#             construction_site = Poi(
#                 coordinate=Point(
#                     feature["geometry"]["coordinates"][0],
#                     feature["geometry"]["coordinates"][1],
#                     srid=4326,
#                 ),
#                 category="construction",
#             )
#             construction_sites.append(construction_site)
#         except Exception as e:
#             print("Failed to create construction site: " + str(e))

#     print(f"{len(construction_sites)} construction successfully created.")

#     Poi.objects.bulk_create(construction_sites)
#     print(f"Imported {len(construction_sites)} construction sites")


def build_overpass_query(bounding_box) -> str:
    """
    Build the query for the overpass API to fetch landmarks.
    """

    assert type(bounding_box) == str, "Bounding box must be a string"
    assert len(bounding_box) > 0, "Bounding box must not be empty"

    TIMEOUT = 120  # The timeout for the API-Request in seconds

    # Build the query
    output_format = "[out:json]"
    timeout = f"[timeout:{TIMEOUT}]"

    categories = ""

    # See: https://wiki.openstreetmap.org/wiki/Key:amenity
    categories += 'node["amenity"]' + bounding_box + ";"
    # See: https://wiki.openstreetmap.org/wiki/Key:historic
    categories += 'node["historic"]' + bounding_box + ";"
    # See: https://wiki.openstreetmap.org/wiki/Key:tourism
    categories += 'node["tourism"]' + bounding_box + ";"
    # See: https://wiki.openstreetmap.org/wiki/Key:leisure
    categories += 'node["leisure"]' + bounding_box + ";"
    # See: https://wiki.openstreetmap.org/wiki/Key:shop
    categories += 'node["shop"]' + bounding_box + ";"

    # See: https://wiki.openstreetmap.org/wiki/Key:public_transport
    categories += 'node["public_transport"]' + bounding_box + ";"
    # See: https://wiki.openstreetmap.org/wiki/Key:man_made
    categories += 'node["man_made"]' + bounding_box + ";"
    # See: https://wiki.openstreetmap.org/wiki/Key:railway
    categories += 'node["railway"]' + bounding_box + ";"
    # See: https://wiki.openstreetmap.org/wiki/Key:bridge
    # get_categories += 'node["bridge"]' + bounding_box + ";" => no results in Dresden
    # See: https://wiki.openstreetmap.org/wiki/Key:sport
    categories += 'node["sport"]' + bounding_box + ";"
    # See: https://wiki.openstreetmap.org/wiki/Key:water
    # get_categories += 'node["water"]' + bounding_box + ";" => no results in Dresden

    suffix = "out;"

    # example: "[out:json][timeout:90];node[amenity=place_of_worship](53.35,9.65,53.75,10.4);out;",
    full_query = f"{output_format}{timeout};({categories});{suffix}"
    return full_query


def import_from_overpass(bounding_box):
    """
    Import landmark data from the overpass API.
    """
    print("Importing land data from overpass turbo")

    query: str = build_overpass_query(bounding_box)
    API = "https://overpass-api.de/api/interpreter"

    try:
        response = requests.post(API, params={"data": query})
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("Failed to fetch landmark data: " + str(e))
        return

    print(f"Fetched {len(data['elements'])} elements.")

    landmark_points = []
    for element in data["elements"]:
        # There should not be any other types than nodes in the response
        if element["type"] != "node":
            print("Found unknown element type: " + element["type"])
            continue

        # There is no easy way to determine the type of landmark from the data
        # There is a tagging system, but it is not used consistently, therefore I try to create a hierarchy of usefull tags

        if "name" in element["tags"]:
            type = element["tags"]["name"]
        elif "amenity" in element["tags"]:
            type = element["tags"]["amenity"]
        elif "brand" in element["tags"]:
            type = element["tags"]["brand"]
        elif "man_made" in element["tags"]:
            type = element["tags"]["man_made"]
        elif "railway" in element["tags"]:
            type = element["tags"]["railway"]
        elif "public_transport" in element["tags"]:
            type = element["tags"]["public_transport"]
        elif "tourism" in element["tags"]:
            type = element["tags"]["tourism"]
        elif "historic" in element["tags"]:
            type = element["tags"]["historic"]
        elif "leisure" in element["tags"]:
            type = element["tags"]["leisure"]
        elif "shop" in element["tags"]:
            type = element["tags"]["shop"]
        elif "sport" in element["tags"]:
            type = element["tags"]["sport"]
        elif "playground" in element["tags"]:
            type = "playground"
        else:
            type = "landmark"

            # Print debug message if no category was found
            tags = ""
            for key in element["tags"]:
                tags += key + " = " + element["tags"][key] + ","
            print(
                "No category found for element with id",
                str(element["id"]),
                "and tags '" + tags + "' using default category",
            )

        # Create a point
        landmark = Landmark(
            coordinate=Point(element["lon"], element["lat"], srid=4326),
            type=type,
            category="landmark",
        )
        landmark_points.append(landmark)

    if len(landmark_points) == 0:
        print("ERROR: No landmarks found in the data")
        return

    Landmark.objects.bulk_create(landmark_points)
    print(f"Imported {len(landmark_points)} landmarks")


class Command(BaseCommand):
    help = """
    Import Landmark for a given area.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "area", type=str, help="The area to fetch landmark data for"
        )

    def handle(self, *args, **options):
        """
        Fetch landmark data.
        """

        BBOX_HAMBURG = "(53.35,9.65,53.75,10.4)"
        BBOX_DRESDEN = "(50.9,13.5,51.2,14.0)"
        USE_DRESDEN = True  # otherwise Hamburg
        bounding_box = BBOX_DRESDEN if USE_DRESDEN else BBOX_HAMBURG

        # # Parse the area argument from the command line args
        # area = options["area"]
        # assert area, "Area is required"

        print("Clearing database")

        try:
            Landmark.objects.filter(category="landmark").delete()
        except Exception as e:
            print("Failed to delete existing landmarks: " + str(e))
            return

        import_from_overpass(bounding_box)
        # import_from_mapdata_service(area)        import_from_mapdata_service(area)
