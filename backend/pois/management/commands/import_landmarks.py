import json

import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from pois.models import Landmark

translation_table: dict = {}
unknown_tags: set = set()
known_tags: set = set()

# See: https://wiki.openstreetmap.org/wiki/Key: + category
OSM_CATEGORIES = [
    "amenity",
    "historic",
    "tourism",
    "leisure",
    "shop",
    "public_transport",
    "man_made",
    "railway",
    "sport",
    # additions
    "aerialway",
    "aeroway",
    "barrier",
    "craft",
    "emergency",
    "healthcare",
    "landuse",
    "miliary",
    "power",
]

# OSM Tags that are not useful and therefore discarded
BLACKLIST = [
    "Bahnübergang",
    "Eisenbahnübergang",
    "Gleisweiche",
]
# Tags "Bahnübergang" und "Eisenbahnübergang" sind häufig nicht hilfreich, da man bei vielen Straßen parallel zu Bahnstrecke fährt


def build_overpass_query(bounding_box: str) -> str:
    """
    Build the query for the overpass API to fetch landmarks.
    """

    global OSM_CATEGORIES

    assert isinstance(bounding_box, str), "Bounding box must be a string"
    assert len(bounding_box) > 0, "Bounding box must not be empty"
    assert len(OSM_CATEGORIES) > 0, "OSM categories must not be empty"

    TIMEOUT = 120  # The timeout for the API-Request in seconds

    # Build the query
    output_format = "[out:json]"
    timeout = f"[timeout:{TIMEOUT}]"

    categories = ""

    # See: https://wiki.openstreetmap.org/wiki/Key: + category
    for category in OSM_CATEGORIES:
        categories += f'node["{category}"]' + bounding_box + ";"

    suffix = "out;"

    # example: "[out:json][timeout:90];node[amenity=place_of_worship](53.35,9.65,53.75,10.4);out;",
    full_query = f"{output_format}{timeout};({categories});{suffix}"
    return full_query


def import_from_overpass(bounding_box: str):
    """
    Import landmark data from the overpass API.
    """

    global OSM_CATEGORIES
    assert len(OSM_CATEGORIES) > 0, "OSM categories must not be empty"

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

        # Always preferentially use the name tag as type
        if "name" in element["tags"]:
            name = element["tags"]["name"]
        else:
            name = ""

        for category in OSM_CATEGORIES:
            if category in element["tags"]:
                # if translate_tag(category, element["tags"][category]) in BLACKLIST:
                #     continue
                type = translate_tag(category, element["tags"][category])
                category = translate_tag(category, "")
                break

        if not category or not type:
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

        if type in BLACKLIST:
            continue

        # Create a Landmark object
        landmark = Landmark(
            id=element["id"],
            name=name,
            coordinate=Point(element["lon"], element["lat"], srid=4326),
            type=type,
            category=category,
            tags=json.dumps(element["tags"]),
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
        PATH = "backend/pois/osm-tags-de.json"
        with open(PATH, "r") as file:
            translation_table = json.load(file)

        assert translation_table, "Translation table is empty"

        import_from_overpass(bounding_box)

        print(
            "Unknown OSM tags: "
            + str(len(unknown_tags))
            + " known tags: "
            + str(len(known_tags))
            + " => "
            + str(
                round(
                    (len(unknown_tags) / (len(known_tags) + len(unknown_tags)) * 100), 2
                )
            )
            + "% untranslated tags"
        )

        for category in unknown_tags:
            print(category)
