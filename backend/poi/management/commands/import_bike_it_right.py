import json

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from poi.models import Construction, Recommendation

# TODO: die gesamte Datei muss wahrscheinlich weg


MAPPING = {
    # DANGERS
    "Unsicheres Gefühl": "danger",
    # "Verhalten Anderer": "danger", # Do not use
    "Schlechtes Fahrgefühl": "danger",
    "Unübersichtliche Infrastruktur": "danger",
    # "Starker Verkehr": "danger", # Do not use
    "Fehlende Infrastruktur": "danger",
    # RECOMMENDATIONS
    "Sicheres Gefühl": "recommendation",
}


class Command(BaseCommand):
    help = """ Import the Bike IT Right data. """

    """
    One bike it right feature has the following format:
    {
        "type": "Feature",
        "id": 1,
        "geometry": {
            "type": "Point",
            "coordinates": [
                568678.8284,
                5934215.5263999999
            ]
        },
        "properties": {
            "OBJECTID": 1,
            "Kategorie": "Unsicheres Gefühl",
            "GlobalID": "{C4D8AACE-E557-4DFD-9D27-73513F38B8F6}",
            "CreationDate": 1655287516134,
            "Rechtswert": 568678.82844679116,
            "Hochwert": 5934215.526418088
        }
    },
    """

    def get_category_name(self, feature):
        base_name = f'BikeITRight_{feature["properties"]["Kategorie"]}'
        id = feature["properties"]["GlobalID"]
        return f"{base_name}_{id}"

    def danger_exists(self, feature):
        return Construction.objects.filter(
            category=self.get_category_name(feature)
        ).exists()

    def recommendation_exists(self, feature):
        return Recommendation.objects.filter(
            category=self.get_category_name(feature)
        ).exists()

    def handle(self, *args, **options):
        print("Importing Bike IT right data...")

        # Import GeoJSON file from data folder.
        with open(
            str(settings.BASE_DIR) + "/data/BikeITRight_Project_aktualisiert.geojson"
        ) as f:
            data = json.load(f)

        print(f"Found {len(data['features'])} Bike IT Right features.")

        new_dangers = []
        new_recommendations = []

        bike_it_right_categories_count = {}

        for feature in data["features"]:
            if feature["properties"]["Kategorie"] not in bike_it_right_categories_count:
                bike_it_right_categories_count[feature["properties"]["Kategorie"]] = 1
            else:
                bike_it_right_categories_count[feature["properties"]["Kategorie"]] += 1

            if feature["properties"]["Kategorie"] not in MAPPING:
                continue

            if MAPPING[feature["properties"]["Kategorie"]] == "danger":
                if self.danger_exists(feature):
                    continue
                try:
                    danger = Construction(
                        category=self.get_category_name(feature),
                        coordinate=Point(
                            feature["geometry"]["coordinates"][0],
                            feature["geometry"]["coordinates"][1],
                            srid=25832,
                        ).transform(settings.LONLAT, clone=True),
                    )
                    new_dangers.append(danger)
                except Exception as e:
                    print("Failed to create danger: " + str(e))
            elif MAPPING[feature["properties"]["Kategorie"]] == "recommendation":
                if self.recommendation_exists(feature):
                    continue
                try:
                    recommendation = Recommendation(
                        category=self.get_category_name(feature),
                        coordinate=Point(
                            feature["geometry"]["coordinates"][0],
                            feature["geometry"]["coordinates"][1],
                            srid=25832,
                        ).transform(settings.LONLAT, clone=True),
                    )
                    new_recommendations.append(recommendation)
                except Exception as e:
                    print("Failed to create recommendation: " + str(e))
            else:
                print("Unsupported category: " + feature["properties"]["Kategorie"])

        print(
            f"{len(new_dangers)} new dangers and {len(new_recommendations)} new recommendations will be created."
        )

        try:
            Construction.objects.bulk_create(new_dangers)
        except Exception as e:
            print("Failed to bulk create dangers: " + str(e))

        print(f"Successfully created {len(new_dangers)} new dangers.")

        try:
            Recommendation.objects.bulk_create(new_recommendations)
        except Exception as e:
            print("Failed to bulk create recommendations: " + str(e))

        print(f"Successfully created {len(new_recommendations)} new recommendations.")

        print("Bike IT Right categories count:")
        for category, count in bike_it_right_categories_count.items():
            print(f"{category}: {count}")
