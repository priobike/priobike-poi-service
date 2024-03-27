import json

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand

from backend.poi.models import Construction


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

    def fetch(self, *args, **options):
        """
        Fetch construction data from priobike-map-data.
        """

        print("Importing construction data from priobike-map-data...")

        # Import GeoJSON file from data folder.
        with open(
            str(settings.BASE_DIR) + "/data/BikeITRight_Project_aktualisiert.geojson"
        ) as f:
            data = json.load(f)

        print(f"Found {len(data['features'])} construction sites.")

        new_construction_sites = []

        for feature in data["features"]:
            try:
                construction_site = Construction(
                    construction_id=self.getId(feature),
                    coordinate=self.getPoint(feature),
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

    def getId(self, feature):
        return f"{feature["id"]}"  # DE.HH.UP_TNS_STECKBRIEF_VISUALISIERUNG_18083

    def getPoint(self, feature):
        point = Point(
            feature["geometry"]["coordinates"][0],
            feature["geometry"]["coordinates"][1],
            srid=25832,
        ).transform(settings.LONLAT, clone=True)
        return point

    def getTitle(self, feature):
        return f"{feature["properties"]["titel"]}"  # Ipanema-Neubau

    def getOrganisation(self, feature):
        return f"{feature["properties"]["organisation"]}"  # Hochbau

    def getReason(self, feature):
        return f"{feature["properties"]["anlass"]}"  # Hochbau

    def getScope(self, feature):
        return f"{feature["properties"]["umfang"]}"  # Die Sydneystraße ist in Richtung Überseering auf einen Fahrstreifen eingeschränkt.

    def getStartDate(self, feature):
        return f"{feature["properties"]["baubeginn"]}"  # 01.09.2020

    def getEndDate(self, feature):
        return f"{feature["properties"]["bauende"]}"  # 31.07.2024

    def getLastUpdate(self, feature):
        return f"{feature["properties"]["letzteaktualisierung"]}"  # 2021-07-12T14:14:25

    def getIsAccessRestricted(self, feature):
        return f"{feature["properties"]["istzugangeingeschraenkt"]}"  # false

    def getIsDisturbance(self, feature):
        return f"{feature["properties"]["iststoerung"]}"  # true

    def getIsHotspot(self, feature):
        return f"{feature["properties"]["isthotspot"]}"  # false

    def getIsReleased(self, feature):
        return f"{feature["properties"]["istfreigegeben"]}"  # true

    def getAddedValue(self, feature):
        return (
            f"{feature["properties"]["mehrwert"]}"  # Neubau von Wohn- und Bürogebäuden
        )

    def getIsOEPNVERestricted(self, feature):
        return f"{feature["properties"]["istoepnveingeschraenkt"]}"  # false

    def getHasInternetLink(self, feature):
        return f"{feature["properties"]["hatinternetlink"]}"  # false

    def getHasDetourDescription(self, feature):
        return f"{feature["properties"]["hatumleitungsbeschreibung"]}"  # false

    def getIsParkingSpaceRestricted(self, feature):
        return f"{feature["properties"]["istparkraumeingeschraenkt"]}"  # false
