import json

import numpy as np
from django.conf import settings
from django.contrib.gis.geos import Point, Polygon
from django.core.management.base import BaseCommand
from poi.models import Construction, ConstructionSpot, Recommendation
from scipy.spatial import ConvexHull
from shapely.geometry import LineString
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon as ShapelyPolygon

CLUSTER_THRESHOLD = 150  # in meters

DUPLICATE_DISTANCE_THRESHOLD = 20  # in meters
DUPLICATE_TIME_THRESHOLD = 20  # in seconds


class Command(BaseCommand):
    help = """ Cluster construction sites and recommendations. """

    """
    Spots model:
    [
        {
            "spot": Construction/Recommendation,
            "distance_to_center": float
        }
    ]
    """

    def sort_spots(self, spots, current_center):
        """Calculate the distance to the center for each spot and sort the spots by distance to the center."""

        sorted_spots = []
        for spot in spots:
            distance_to_center = spot["spot"].coordinate.distance(current_center)
            sorted_spots.append(
                {"spot": spot["spot"], "distance_to_center": distance_to_center}
            )

        # Sort spots by distance to center
        sorted_spots = sorted(sorted_spots, key=lambda spot: spot["distance_to_center"])

        return sorted_spots

    def get_center(self, spots):
        """Returns the center of the cluster."""

        # Because the coordinates are very close to each other, we can assume a planar coordinate system
        # and don't need to perform corrections for the curvature of the earth.
        center_coordinate_x = 0
        center_coordinate_y = 0

        for spot in spots:
            center_coordinate_x += spot.coordinate.x
            center_coordinate_y += spot.coordinate.y

        center_coordinate_x /= len(spots)
        center_coordinate_y /= len(spots)

        return Point(
            center_coordinate_x, center_coordinate_y, srid=spots[0].coordinate.srid
        )

    def get_construction_spot(self, cluster):
        """Returns a construction spot object for the given cluster."""

        construction_spot_value = 0
        for spot in cluster:
            if isinstance(spot, Construction):
                construction_spot_value += 1
            else:
                construction_spot_value -= 1

        # First get a unique list of points (remove duplicate coordinates).
        unique_points = []
        for spot in cluster:
            if spot.coordinate not in unique_points:
                unique_points.append(spot.coordinate)

        # Create polygon around point(s)
        border_points = []
        buffer_value = 0.0001
        if len(unique_points) == 1:
            # Add padding around spot
            point = ShapelyPoint(unique_points[0].x, unique_points[0].y)
            buffered_point = point.buffer(buffer_value)
            border_points = buffered_point.exterior.coords
        elif len(unique_points) == 2:
            # Add padding around line
            line = LineString(
                [
                    (unique_points[0].x, unique_points[0].y),
                    (unique_points[1].x, unique_points[1].y),
                ]
            )
            buffered_line = line.buffer(buffer_value)
            border_points = buffered_line.exterior.coords
        else:
            # Add padding around polygon
            points = np.array(
                [[coordinate.x, coordinate.y] for coordinate in unique_points]
            )
            try:
                convex_hull = ConvexHull(points)
                points = points[convex_hull.vertices]
                point = points + [points[0]]
                polygon = ShapelyPolygon(points)
                buffered_polygon = polygon.buffer(buffer_value)
                border_points = buffered_polygon.exterior.coords
            except:
                print(
                    f"Convex hull creation failed for points: {points} - Falling back to line buffer."
                )
                line = LineString(
                    [[unique_point.x, unique_point.y] for unique_point in unique_points]
                )
                buffered_line = line.buffer(buffer_value)
                border_points = buffered_line.exterior.coords

        # Convert from shapely points to django points
        django_points = [
            Point(point[0], point[1], srid=cluster[0].coordinate.srid)
            for point in border_points
        ]

        return ConstructionSpot(
            coordinate=self.get_center(cluster),
            value=construction_spot_value,
            border=Polygon(django_points, srid=cluster[0].coordinate.srid),
        )

    def find_unique(self, list):
        """Given a list of Construction sites or Recommendations this method returns a list of unique Construction sites or Recommendations."""

        original_srid = list[0].coordinate.srid

        for element in list:
            element.coordinate.transform(settings.METRICAL, clone=False)

        unique_list = []

        for element in list:
            if len(unique_list) == 0:
                unique_list.append(element)
            else:
                duplicate_already_exists = False
                for unique_element in unique_list:
                    if unique_element.pk == element.pk:
                        continue
                    unique_construction_coordinate = (
                        unique_element.coordinate.transform(
                            settings.METRICAL, clone=True
                        )
                    )
                    construction_coordinate = element.coordinate.transform(
                        settings.METRICAL, clone=True
                    )
                    if (
                        unique_construction_coordinate.distance(construction_coordinate)
                        < DUPLICATE_DISTANCE_THRESHOLD
                        and abs(
                            unique_element.date.timestamp() - element.date.timestamp()
                        )
                        < DUPLICATE_TIME_THRESHOLD
                    ):
                        duplicate_already_exists = True
                        break
                if not duplicate_already_exists:
                    unique_list.append(element)

        for element in unique_list:
            element.coordinate.transform(original_srid, clone=False)

        return unique_list

    def create_geojson(self, list, filename):
        """Creates a GeoJSON file for the given list of Construction or Recommendations. Used for debugging. q"""

        geojson = {"type": "FeatureCollection", "features": []}

        for element in list:
            geojson["features"].append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [element.coordinate.x, element.coordinate.y],
                    },
                    "properties": {
                        "category": element.category,
                        "date": element.date.timestamp(),
                    },
                }
            )

        # Write geojson to file in static folder
        with open(
            str(settings.BASE_DIR) + f"/data/construction_spots/{filename}", "w"
        ) as file:
            json.dump(geojson, file)

    def handle(self, *args, **options):
        print("Clustering constructions and recommendations...")

        all_constructions = list(Construction.objects.all())
        all_recommendations = list(Recommendation.objects.all())

        print("Removing duplicates...")
        unique_constructions = self.find_unique(all_constructions)
        unique_recommendations = self.find_unique(all_recommendations)
        print(
            f"Found {len(all_constructions)} constructions and {len(all_recommendations)} recommendations."
        )
        print(
            f"Found {len(unique_constructions)} unique constructions and {len(unique_recommendations)} unique recommendations."
        )

        clusters = []

        first_spot = unique_constructions[0]
        current_center = first_spot.coordinate

        objects = unique_constructions[1:] + unique_recommendations

        spots = []
        for spot in objects:
            current_center = current_center.transform(settings.METRICAL, clone=True)
            spot.coordinate = spot.coordinate.transform(settings.METRICAL, clone=True)
            distance_to_center = spot.coordinate.distance(current_center)
            spots.append({"spot": spot, "distance_to_center": distance_to_center})

        # Sort spots by distance to center
        spots = sorted(spots, key=lambda spot: spot["distance_to_center"])

        clusters.append([first_spot])

        while len(spots) > 0:
            if spots[0]["distance_to_center"] < CLUSTER_THRESHOLD:
                clusters[-1].append(spots[0]["spot"])
                center_diff_x = current_center.x - spots[0]["spot"].coordinate.x
                center_diff_y = current_center.y - spots[0]["spot"].coordinate.y
                factor = 1 / len(clusters[-1])
                current_center.x -= center_diff_x * factor
                current_center.y -= center_diff_y * factor
            else:
                clusters.append([spots[0]["spot"]])
                current_center = spots[0]["spot"].coordinate

            spots.pop(0)
            spots = self.sort_spots(spots, current_center)

        print(f"Created {len(clusters)} clusters.")

        # Transform the coordinates back to lon lat.
        for cluster in clusters:
            for spot in cluster:
                spot.coordinate = spot.coordinate.transform(settings.LONLAT, clone=True)

        construction_spots = []

        for cluster in clusters:
            construction_spots.append(self.get_construction_spot(cluster))

        print(f"Deleting {ConstructionSpot.objects.count()} old construction spots...")
        try:
            ConstructionSpot.objects.all().delete()
            ConstructionSpot.objects.bulk_create(construction_spots)
        except Exception as e:
            print("Failed to create new construction spots: " + str(e))

        print(f"Created {len(construction_spots)} construction spots.")
        print("Done.")

        print("Creating GeoJSON file with clusters...")

        if len(construction_spots) != ConstructionSpot.objects.count() or len(
            clusters
        ) != len(construction_spots):
            print(
                "Error: Something went wrong during the creation of clusters and construction sports. GeoJSON file will not be created."
            )
            return

        geojson = {"type": "FeatureCollection", "features": []}

        for i in range(len(construction_spots)):
            # Add center of cluster as point to geojson
            geojson["features"].append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [
                            construction_spots[i].coordinate.x,
                            construction_spots[i].coordinate.y,
                        ],
                    },
                    "properties": {"value": construction_spots[i].value},
                }
            )

            # Add polygon of cluster to geojson
            try:
                geojson["features"].append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            # First point needs to be repeated at the end to close the polygon
                            "coordinates": construction_spots[i].border.coords,
                        },
                        "properties": {"value": construction_spots[i].value},
                    }
                )
            except Exception as e:
                print("Failed to create polygon for cluster: " + str(e))

        # Write geojson to file in static folder
        with open(
            str(settings.BASE_DIR)
            + "/data/construction_spots/construction_spots_cluster.geojson",
            "w",
        ) as file:
            json.dump(geojson, file)

        print("Done creating GeoJSON.")
