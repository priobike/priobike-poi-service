import json

from django.conf import settings
from django.contrib.gis.geos import LineString, Point
from django.contrib.gis.measure import D
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from pois.models import Poi, PoiLine


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
        if (segments[index][1] >= segments[i][0]):
            segments[index][1] = max(segments[index][1], segments[i][1])
        else:
            index = index + 1
            segments[index] = segments[i]
 
    # Now arr[0..index] stores the merged Intervals
    return segments[:index + 1]


def get_segments(type_of_poi, route_linestring, elongation, threshold):
    """
    Make segments around found pois on the route.
    Overlaps between segments are merged into one segment.
    Elongation defines how much points are elongated to a line along the route.
    """

    route_lstr_mercator = route_linestring.transform(settings.METRICAL, clone=True)
    route_length_mercator = route_lstr_mercator.length

    nearby_point_pois = Poi.objects \
        .filter(category=type_of_poi) \
        .filter(coordinate__distance_lt=(route_linestring, D(m=threshold)))
    nearby_line_pois_intersecting = PoiLine.objects \
        .filter(category=type_of_poi) \
        .filter(line__distance_lt=(route_linestring, D(m=threshold)))
    
    # Only use the line segments inside the buffered region
    route_lstr_buffered = route_lstr_mercator.buffer(threshold)
    nearby_line_pois_on_route = []
    for poi in nearby_line_pois_intersecting:
        line_on_route = poi.line \
            .transform(settings.METRICAL, clone=True) \
            .intersection(route_lstr_buffered)
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
        poi_coordinate_mercator = poi.coordinate.transform(settings.METRICAL, clone=True)
        dist_on_route = route_lstr_mercator.project(poi_coordinate_mercator)
        dist_start = max(0, dist_on_route - elongation)
        dist_end = min(route_length_mercator, dist_on_route + elongation)
        segments.append([dist_start, dist_end])
    for line in nearby_line_pois_on_route:
        dist_start = route_lstr_mercator.project(Point(line.coords[0], srid=settings.METRICAL))
        dist_end = route_lstr_mercator.project(Point(line.coords[-1], srid=settings.METRICAL))
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
            break # Projected all segments

        from_coord = Point(route_lstr_mercator.coords[i], srid=settings.METRICAL)
        to_coord = Point(route_lstr_mercator.coords[i + 1], srid=settings.METRICAL)
        to_dist = from_dist + from_coord.distance(to_coord)

        x = segments[0][0]
        y = segments[0][1]
        a = from_dist
        b = to_dist

        from_dist = to_dist # Update from_dist for next iteration

        # Skipped a segment
        # Segment:   x--y
        # Route:    a----b
        if x >= a and y <= b:
            # Add the projected segment directly
            projected_segments.append([
                route_lstr_mercator.interpolate(segments[0][0]), 
                route_lstr_mercator.interpolate(segments[0][1]),
            ])
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
            if running_segment is None: # May happen when there is an exact overlap
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
        [
            point.transform(settings.LONLAT, clone=True)
            for point in segment
        ]
        for segment in projected_segments
    ]
    # Point object is not serializable, so we convert it to a list of coordinates
    projected_segments_json = [
        [
            [point.x, point.y]
            for point in segment
        ]
        for segment in projected_segments
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
            route_linestring: LineString = LineString(route_points, srid=settings.LONLAT)
        except ValueError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid route points"}))

        response_json = { "success": True }

        for type_of_poi in ["construction", "accidenthotspot", "greenwave", "veloroute"]:
            response_json[f"{type_of_poi}s"] = get_segments(
                type_of_poi,
                route_linestring, 
                elongation,
                threshold,
            )

        return JsonResponse(response_json)
