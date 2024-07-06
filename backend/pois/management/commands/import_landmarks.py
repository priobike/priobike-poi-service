import json

import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from pois.models import Landmark

translation_table: dict = {}
unknown_tags: set = set()
known_tags: set = set()

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


def build_overpass_query(bounding_box: str) -> str:
    """
    Build the query for the overpass API to fetch landmarks.
    """

    assert isinstance(bounding_box, str), "Bounding box must be a string"
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


def import_from_overpass(bounding_box: str):
    """
    Import landmark data from the overpass API.
    """
    print("Importing landmark data from overpass turbo")

    query: str = build_overpass_query(bounding_box)
    API = "https://overpass-api.de/api/interpreter"

    try:
        response = requests.get(API, params={"data": query})
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

        assert element["id"] is not None, "Element id is required"

        # There is no easy way to determine the type of landmark from the data
        # There is a tagging system, but it is not used consistently, therefore I try to create a hierarchy of usefull tags

        # Data structure:
        # type = i.e. "Kino"
        # category = i.e. "amenity" (the category used by openstreetmap/overpass)

        # TODO: refactore this

        if "name" in element["tags"]:
            type = element["tags"]["name"]
            if "amenity" in element["tags"]:
                category = translate_tag("amenity", "")
            elif "brand" in element["tags"]:
                category = translate_tag("brand", "")
            elif "man_made" in element["tags"]:
                category = translate_tag("man_made", "")
            elif "railway" in element["tags"]:
                category = translate_tag("railway", "")
            elif "public_transport" in element["tags"]:
                category = translate_tag("public_transport", "")
            elif "tourism" in element["tags"]:
                category = translate_tag("tourism", "")
            elif "historic" in element["tags"]:
                category = translate_tag("historic", "")
            elif "leisure" in element["tags"]:
                category = translate_tag("leisure", "")
            elif "shop" in element["tags"]:
                category = translate_tag("shop", "")
            elif "sport" in element["tags"]:
                category = translate_tag("sport", "")
            elif "playground" in element["tags"]:
                category = "Spielplatz"
            else:
                category = "Landmarke"

        elif "amenity" in element["tags"]:
            type = translate_tag("amenity", element["tags"]["amenity"])
            category = translate_tag("amenity", "")
        elif "brand" in element["tags"]:
            type = element["tags"]["brand"]  # use brand as type, i.e. "McDonalds"
            category = translate_tag("brand", "")
        elif "man_made" in element["tags"]:
            type = translate_tag("man_made", element["tags"]["man_made"])
            category = translate_tag("man_made", "")
        elif "railway" in element["tags"]:
            type = translate_tag("railway", element["tags"]["railway"])
            category = translate_tag("railway", "")
        elif "public_transport" in element["tags"]:
            type = translate_tag(
                "public_transport", element["tags"]["public_transport"]
            )
            category = translate_tag("public_transport", "")
        elif "tourism" in element["tags"]:
            type = translate_tag("tourism", element["tags"]["tourism"])
            category = translate_tag("tourism", "")
        elif "historic" in element["tags"]:
            type = translate_tag("historic", element["tags"]["historic"])
            category = translate_tag("historic", "")
        elif "leisure" in element["tags"]:
            type = translate_tag("leisure", element["tags"]["leisure"])
            category = translate_tag("leisure", "")
        elif "shop" in element["tags"]:
            type = translate_tag("shop", element["tags"]["shop"])
            category = translate_tag("shop", "")
        elif "sport" in element["tags"]:
            type = translate_tag("sport", element["tags"]["sport"])
            category = translate_tag("sport", "")
        elif "playground" in element["tags"]:
            type = "Spielplatz"
            category = "Spielplatz"
        else:
            type = "Landmarke"
            category = "Landmarke"

            # Print debug message if no category was found
            tags = ""
            for key in element["tags"]:
                tags += key + " = " + element["tags"][key] + ","
            print(
                "No category found for element with id",
                str(element["id"]),
                "and tags '" + tags + "' using default category",
            )

        # TODO: I could also just discard the landmarks if I have no valid translation

        # Create a Landmark object
        landmark = Landmark(
            id=element["id"],
            coordinate=Point(element["lon"], element["lat"], srid=4326),
            type=type,
            category=category,
        )
        landmark_points.append(landmark)

    if len(landmark_points) == 0:
        print("ERROR: No landmarks found in the data")
        return

    Landmark.objects.bulk_create(landmark_points)
    print(f"Imported {len(landmark_points)} landmarks")


def translate_tag(category: str, tag: str) -> str:
    """
    Helper function to translate the osm tags to german.
    Source for the translation table: https://github.com/plepe/openstreetmap-tag-translations/blob/master/tags/de.json
    """

    # Example:
    # "tag:amenity=cinema": {
    #   "message": "Kino",
    #   "description": "Tag \"amenity=cinema\". See https://wiki.openstreetmap.org/wiki/Tag:amenity=cinema"
    # },

    global translation_table
    global unknown_tags
    global known_tags

    assert category, "Category is required"
    assert translation_table, "Translation table is empty"

    # if tag is empty, only translate the category
    if tag == "":
        key = "tag:" + category
        default_return = category
    else:
        key = "tag:" + category + "=" + tag
        default_return = tag

    if key in translation_table and translation_table[key]["message"]:
        known_tags.add(key)
        return translation_table[key]["message"]

    unknown_tags.add(key)
    return default_return


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

        # Parse the area argument from the command line args
        area = options["area"]
        assert area, "Area is required"
        # TODO: use the area argument to determine the bounding box

        BBOX_HAMBURG = "(53.35,9.65,53.75,10.4)"
        BBOX_DRESDEN = "(50.9,13.5,51.2,14.0)"
        USE_DRESDEN = True  # otherwise Hamburg
        bounding_box = BBOX_DRESDEN if USE_DRESDEN else BBOX_HAMBURG

        # # Parse the area argument from the command line args
        # area = options["area"]
        # assert area, "Area is required"

        print("Clearing database")

        try:
            Landmark.objects.all().delete()
        except Exception as e:
            print("Failed to delete existing landmarks: " + str(e))
            return

        global translation_table

        # load translation table for osm tags
        PATH = "backend/pois/openstreetbrowser-osm-tags-de.json"
        with open(PATH, "r") as file:
            translation_table = json.load(file)

        assert translation_table, "Translation table is empty"

        import_from_overpass(bounding_box)

        print(
            "Unknown OSM tags: "
            + str(len(unknown_tags))
            + " known tags: "
            + str(len(known_tags))
            + "=> "
            + str(len(known_tags) / (len(known_tags) + len(unknown_tags)) * 100)
            + "%"
        )

        output_limiter = 0
        for category in unknown_tags:
            print("Unknown OSM tags for translation:", category)
            output_limiter += 1
            if output_limiter >= 20:
                print("...and more")
                break

        # import_from_mapdata_service(area)        import_from_mapdata_service(area)
