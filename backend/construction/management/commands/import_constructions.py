import json

from construction.models import Construction
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = """ Import the Construction data. """

    """
    One feature from priobike-map-data has the following format:
    {
        "type": "Feature",
        "id": "DE.HH.UP_TNS_STECKBRIEF_VISUALISIERUNG_18083",
        "geometry": {
            "type": "Point",
            "coordinates": [
                10.015726348379959,
                53.604443029305926
            ]
        },
        "properties": {
            "titel": "Ipanema-Neubau",
            "organisation": "Hochbau",
            "anlass": "Hochbau",
            "umfang": "Die Sydneystra\u00dfe ist in Richtung \u00dcberseering auf einen Fahrstreifen eingeschr\u00e4nkt.",
            "baubeginn": "01.09.2020",
            "bauende": "31.07.2024",
            "letzteaktualisierung": "2021-07-12T14:14:25",
            "istzugangeingeschraenkt": false,
            "iststoerung": true,
            "isthotspot": false,
            "istfreigegeben": true,
            "mehrwert": "Neubau von Wohn- und B\u00fcrogeb\u00e4uden",
            "istoepnveingeschraenkt": false,
            "hatinternetlink": false,
            "hatumleitungsbeschreibung": false,
            "istparkraumeingeschraenkt": false,
            "id": "construction_sites-0"
        },
        "srsName": "EPSG:4326"
    },
    """

    def get_name(self, feature):
        return feature["id"]  # example: DE.HH.UP_TNS_STECKBRIEF_VISUALISIERUNG_18083

    def get_point(self, feature):
        point = Point(
            feature["geometry"]["coordinates"][0],
            feature["geometry"]["coordinates"][1],
            srid=4326,
        )
        return point

    def handle(self, *args, **options):
        """
        Fetch construction data from priobike-map-data.
        """

        print("Importing construction data from priobike-map-data...")

        # Import GeoJSON file from data folder.
        with open(
            str(settings.BASE_DIR)
            + "/sample-construction-sites-v2.geojson"  # TODO: use real data
        ) as f:
            data = json.load(f)

        print(f"Found {len(data['features'])} construction sites.")

        try:
            Construction.objects.all().delete()
        except Exception as e:
            print("Failed to delete existing construction sites: " + str(e))

        new_construction_sites = []

        for feature in data["features"]:
            try:
                construction_site = Construction(
                    name=self.get_name(feature),
                    coordinate=self.get_point(feature),
                )
                new_construction_sites.append(construction_site)
            except Exception as e:
                print("Failed to create construction site: " + str(e))

        print(f"{len(new_construction_sites)} construction sites successfully created.")

        try:
            Construction.objects.bulk_create(new_construction_sites)
        except Exception as e:
            print("Failed to bulk create construction sites: " + str(e))

        print(
            f"Successfully created {len(new_construction_sites)} new construction sites."
        )
