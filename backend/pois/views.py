import json
import time

from django.conf import settings
from django.contrib.gis.geos import LineString, Point
from django.contrib.gis.measure import D
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from pois.models import Landmark, Poi, PoiLine

# A list of OSM Tags that are only used for matching of landmarks, if no others is found and if they are really close
LOW_PRIORITY_TAGS = [
    "Mülleimer",
    "Fahrradständer",
    "Gullydeckel",
    "Stolperstein",
    "Mast",
    "Überwachungskamera",
    "Unterstand",
    "Sitzbank",
    "Oberleitungsmast",
    "Überwachungsstation",
    "Bahn-Signal",
    "Grenzstein",
    "Poller",
]
# Ich sollte die vielleicht doch mit einbeziehen, weil man ja durch die Richtungseingabe schon in der Regel eindeutig sieht, wo das stehen soll.


def merge_segments(segments):
    """
    Merge overlapping segments.
    """
    # Order by start distance
    segments = sorted(segments, key=lambda x: x[0])

    # Stores index of last element
    # in output array (modified arr[])
    index = 0

    # Traverse all input Intervals starting from
    # second interval
    for i in range(1, len(segments)):
        # If this is not first Interval and overlaps
        # with the previous one, Merge previous and
        # current Intervals
        if segments[index][1] >= segments[i][0]:
            segments[index][1] = max(segments[index][1], segments[i][1])
        else:
            index = index + 1
            segments[index] = segments[i]

    # Now arr[0..index] stores the merged Intervals
    return segments[: index + 1]


def get_segments(type_of_poi, route_linestring, elongation, threshold):
    """
    Make segments around found pois on the route.
    Overlaps between segments are merged into one segment.
    Elongation defines how much points are elongated to a line along the route.
    """

    route_lstr_mercator = route_linestring.transform(settings.METRICAL, clone=True)
    route_length_mercator = route_lstr_mercator.length

    nearby_point_pois = Poi.objects.filter(category=type_of_poi).filter(
        coordinate__distance_lt=(route_linestring, D(m=threshold))
    )
    nearby_line_pois_intersecting = PoiLine.objects.filter(category=type_of_poi).filter(
        line__distance_lt=(route_linestring, D(m=threshold))
    )

    # Only use the line segments inside the buffered region
    route_lstr_buffered = route_lstr_mercator.buffer(threshold)
    nearby_line_pois_on_route = []
    for poi in nearby_line_pois_intersecting:
        line_on_route = poi.line.transform(settings.METRICAL, clone=True).intersection(
            route_lstr_buffered
        )
        if len(line_on_route.coords) == 0:
            continue
        # Check if line is multiline
        if line_on_route.geom_type == "MultiLineString":
            for partial_line in line_on_route:
                nearby_line_pois_on_route.append(partial_line)
        else:
            nearby_line_pois_on_route.append(line_on_route)

    if not nearby_point_pois and not nearby_line_pois_on_route:
        return []

    # Match each coordinate onto the route in the mercator projection
    segments = []
    for poi in nearby_point_pois:
        poi_coordinate_mercator = poi.coordinate.transform(
            settings.METRICAL, clone=True
        )
        dist_on_route = route_lstr_mercator.project(poi_coordinate_mercator)
        dist_start = max(0, dist_on_route - elongation)
        dist_end = min(route_length_mercator, dist_on_route + elongation)
        segments.append([dist_start, dist_end])
    for line in nearby_line_pois_on_route:
        dist_start = route_lstr_mercator.project(
            Point(line.coords[0], srid=settings.METRICAL)
        )
        dist_end = route_lstr_mercator.project(
            Point(line.coords[-1], srid=settings.METRICAL)
        )
        if dist_start > dist_end:
            dist_start, dist_end = dist_end, dist_start
        segments.append([dist_start, dist_end])

    segments = merge_segments(segments)

    # Convert the segments to actual coordinates on the route, by traversing the route
    # and finding the corresponding points for each segment
    projected_segments = []
    from_dist = 0
    running_segment = None
    # Iterate through all coordinates of the route
    for i in range(len(route_lstr_mercator.coords) - 1):
        if len(segments) == 0:
            break  # Projected all segments

        from_coord = Point(route_lstr_mercator.coords[i], srid=settings.METRICAL)
        to_coord = Point(route_lstr_mercator.coords[i + 1], srid=settings.METRICAL)
        to_dist = from_dist + from_coord.distance(to_coord)

        x = segments[0][0]
        y = segments[0][1]
        a = from_dist
        b = to_dist

        from_dist = to_dist  # Update from_dist for next iteration

        # Skipped a segment
        # Segment:   x--y
        # Route:    a----b
        if x >= a and y <= b:
            # Add the projected segment directly
            projected_segments.append(
                [
                    route_lstr_mercator.interpolate(segments[0][0]),
                    route_lstr_mercator.interpolate(segments[0][1]),
                ]
            )
            segments.pop(0)
            continue

        # Entered a new segment
        # Segment:   x--
        # Route:   a---b
        if x >= a and x <= b:
            # Start a new segment
            running_segment = []
            running_segment.append(route_lstr_mercator.interpolate(segments[0][0]))
            running_segment.append(to_coord)

        # Inside a segment
        # Segment: x-------y
        # Route:     a---b
        if x <= a and y >= b:
            if running_segment is None:  # May happen when there is an exact overlap
                running_segment = []
            running_segment.append(from_coord)
            running_segment.append(to_coord)

        # Exited a segment
        # Segment:   --y
        # Route:     a---b
        if y >= a and y <= b:
            if running_segment is None:
                running_segment = []
            running_segment.append(from_coord)
            running_segment.append(route_lstr_mercator.interpolate(segments[0][1]))

            # Reset running segment
            projected_segments.append(running_segment)
            running_segment = None
            segments.pop(0)

    # Transform all segments back to lonlat
    projected_segments = [
        [point.transform(settings.LONLAT, clone=True) for point in segment]
        for segment in projected_segments
    ]
    # Point object is not serializable, so we convert it to a list of coordinates
    projected_segments_json = [
        [[point.x, point.y] for point in segment] for segment in projected_segments
    ]
    return projected_segments_json


@method_decorator(csrf_exempt, name="dispatch")
class MatchPoisResource(View):
    def post(self, request):
        """
        Determine which pois are on a given route.
        """

        try:
            json_data = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid request."}))

        threshold = json_data.get("threshold", 5)
        # Make sure threshold is a positive integer
        if not isinstance(threshold, int) or threshold < 0:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid threshold."}))

        elongation = json_data.get("elongation", 20)
        # Make sure elongation is a positive float
        if not isinstance(elongation, int) or elongation < 0:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid elongation."}))

        route = json_data.get("route")
        if not route:
            return HttpResponseBadRequest(json.dumps({"error": "No route data"}))

        try:
            route_points = [(point["lon"], point["lat"]) for point in route]
        except KeyError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid route data"}))

        try:
            route_linestring: LineString = LineString(
                route_points, srid=settings.LONLAT
            )
        except ValueError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid route points"}))

        response_json = {"success": True}

        for type_of_poi in [
            "construction",
            "accidenthotspot",
            "greenwave",
            "veloroute",
        ]:
            response_json[f"{type_of_poi}s"] = get_segments(
                type_of_poi,
                route_linestring,
                elongation,
                threshold,
            )

        return JsonResponse(response_json)


@method_decorator(csrf_exempt, name="dispatch")
class MatchLandmarksResource(View):
    def post(self, request):
        """
        Determine which landmarks are on a given route.
        """
        try:
            json_data: dict = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid request."}))

        # get query parameters
        replace_graphhopper_query = False
        try:
            replace_instructions = str(request.GET.get("replaceInstructions", "false"))
            if replace_instructions.lower() == "true":
                replace_graphhopper_query = True
                print("Replace Graphhopper query. replace_graphhopper_query == True")
            else:
                print("Extend Graphhopper query. replace_graphhopper_query == False")
        except Exception:
            print(
                "Exception when checkingreplaceInstructions 'replaceInstructions' query parameter => Extend Graphhopper query"
            )

        route = json_data.get("points")
        if not route:
            return HttpResponseBadRequest(json.dumps({"error": "No route data"}))

        route_points = {}
        index = 0
        try:
            for point in route["coordinates"]:
                route_points[index] = {"lat": point[1], "lon": point[0]}
                index += 1

        except KeyError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid route data"}))

        """
        Result: route points as dictionary
        "0": {"lat": 51.03015, "lon": 13.730835},
        "1": {"lat": 51.030206, "lon": 13.730826},
        "2": {"lat": 51.030301, "lon": 13.730626},
        """

        if not route_points:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid route points"}))
        if len(route_points) < 2:
            return HttpResponseBadRequest(
                json.dumps({"error": "Route must have at least 2 points"})
            )

        # Determine decision points on the route by taking the last point of each segments and use the according coordinates based on the index

        # Gets the intervals for each instruction and determine the according coordinates for the last point of each interval, i.e. the decision point
        instructions = json_data.get("instructions")

        if not instructions:
            return HttpResponseBadRequest(json.dumps({"error": "No instructions data"}))

        timestamp_before = time.time()

        # for statistics, keep track of how many landmarks were found
        landmarks_found = 0

        # Don't use last element as it is the destination, therefore it has the same interval as the previous element
        for segment in instructions[:-1]:
            # Get the last index of the interval and determine the associated coordinates
            segment_index: int = segment["interval"][0]
            coord: dict = route_points[segment_index]
            point_lon = coord["lon"]
            point_lat = coord["lat"]

            decision_point = Point(point_lon, point_lat, srid=settings.LONLAT)
            landmark = match_landmark_to_decisionpoint(decision_point)

            # if landmark found, add it to the text of the graphhopper request
            # if no landmark found, keep the instruction as it is
            if landmark:
                landmark["direction"] = determine_direction_landmark(
                    segment_index, route_points, landmark
                )
                text: str = ""
                # wheather to replace the graphhopper query or extend it
                if replace_graphhopper_query:
                    text = (
                        "bei "
                        + landmark["type"]
                        + " "
                        + landmark["name"]
                        + " "
                        + landmark["direction"]
                        + " "
                        + translate_graphopper_sign(int(segment["sign"]))
                    )
                else:
                    text = (
                        "bei "
                        + landmark["type"]
                        + " "
                        + landmark["name"]
                        + " "
                        + landmark["direction"]
                        + " "
                        + segment["text"]
                    )

                segment["text"] = text
                landmarks_found += 1
                segment["landmark"] = landmark

        timestamp_after = time.time()
        length_route = len(route_points)
        print(
            f"Statistics: {round((timestamp_after - timestamp_before),2)} seconds needed for matching landmarks with route with {length_route} points"
        )
        print(
            f"Statistics: {landmarks_found} landmarks found for {len(instructions[:-1])} segments"
        )

        return JsonResponse(json_data)


def match_landmark_to_decisionpoint(decision_point: Point) -> dict:
    """
    Match a landmark to a decision point on the route.
    """

    # The Treshold in meters to match a landmark to a decision point
    # It is set by the app and send with the request, otherwise use the default
    TRESHOLD = 30
    TRESHOLD_LOW_PRIORITY: int = round(TRESHOLD * 0.5)

    point_mercator = decision_point.transform(settings.METRICAL, clone=True)

    found_landmark = None

    # Check which landmark are within the threshold to the ecision point
    for landmark in Landmark.objects.filter(
        coordinate__distance_lt=(point_mercator, D(m=TRESHOLD))
    ):
        landmark_mercator = landmark.coordinate.transform(settings.METRICAL, clone=True)
        distance: float = point_mercator.distance(landmark_mercator)

        # Check if there is already a landmark found and/or check if the new landmark is closer than the already found landmark
        if found_landmark:
            # Low priority landmarks are only considered if they are closer
            if landmark.type in LOW_PRIORITY_TAGS:
                if distance > TRESHOLD_LOW_PRIORITY:
                    continue
                # Also check tags
                for tag in landmark.tags:
                    if tag in LOW_PRIORITY_TAGS:
                        continue

            old_distance = float(found_landmark["distance"])
            if distance >= old_distance:
                continue

        found_landmark = {
            "id": landmark.id,
            "name": landmark.name,
            "category": landmark.category,
            "type": landmark.type,
            "lat": landmark.coordinate.y,
            "lon": landmark.coordinate.x,
            "distance": distance,
            "osm_tags": json.loads(landmark.tags),
        }

    # If it enough to keep the distance with 4 decimal places
    if found_landmark:
        found_landmark["distance"] = round(found_landmark["distance"], 4)

    return found_landmark


def determine_direction_landmark(
    segment_index: int, route_points: dict, landmark: dict
) -> str:
    """
    Determine the direction of the landmark by checking the current and the previous point of the route.
    With that line, we can determine if the landmark is on the left or right side relative to the line.
    """

    # Get own direction by checking previous and current position
    if segment_index == 0:
        # edge case for first segment
        current_coords = route_points[segment_index + 1]
        previous_coords = route_points[segment_index]
    else:
        # normal case
        current_coords = route_points[segment_index]
        previous_coords = route_points[segment_index - 1]

    difference_lat = current_coords["lat"] - previous_coords["lat"]  # east-west-axis
    difference_lon = current_coords["lon"] - previous_coords["lon"]  # north-south-axis

    # positive lon => east
    # negative lon => west
    # positive lat => north
    # negative lat => south

    # Lat = Breitengrad
    # Lon = Längengrad

    # Determine own direction by checking in which direction we moved more
    if abs(difference_lat) > abs(difference_lon):
        # more movement along the north-south-axis
        if difference_lat > 0:
            # we move to the north
            if landmark["lon"] > current_coords["lon"]:
                return "auf rechter Seite"
            else:
                return "auf linker Seite"
        else:
            # we move to the south
            if landmark["lon"] > current_coords["lon"]:
                return "auf linker Seite"
            else:
                return "auf rechter Seite"
    else:
        # more movement along the east-west-axis
        if difference_lon > 0:
            # we move to the east
            if landmark["lat"] > current_coords["lat"]:
                return "auf linker Seite"
            else:
                return "auf rechter Seite"
        else:
            # we move to the west
            if landmark["lat"] > current_coords["lat"]:
                return "auf rechter Seite"
            else:
                return "auf linker Seite"


def translate_graphopper_sign(sign: int) -> str:
    """
    Translates the graphhopper sign to an actual instruction.
    See: https://docs.graphhopper.com/#operation/getRoute => Responses => paths => instructions
    """

    if sign == -98:
        return "wenden"
    if sign == -8:
        return "links wenden"
    if sign == -7:
        return "links halten"
    if sign == -6:
        return "Kreisverkehr verlassen"
    if sign == -3:
        return "scharf links abbiegen"
    if sign == -2:
        return "links abbiegen"
    if sign == -1:
        return "leicht links abbiegen"
    if sign == 0:
        return "geradeaus weiter"
    if sign == 1:
        return "leicht rechts abbiegen"
    if sign == 2:
        return "rechts abbiegen"
    if sign == 3:
        return "scharf rechts abbiegen"
    if sign == 4:
        return "Ziel erreicht"
    if sign == 5:
        return "Zwischenziel erreicht"
    if sign == 6:
        return "in den Kreisverkehr fahren"
    if sign == 7:
        return "rechts halten"
    if sign == 8:
        return "rechts wenden"

    print(f"Sign {sign} not found")
    return ""
