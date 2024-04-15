import json
from typing import List

from django.conf import settings
from django.contrib.gis.geos import LineString, Point
from django.contrib.gis.measure import D
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from pois.models import Poi, PoiLine


def points_in_route_dir(linestring: LineString, route: LineString, system=settings.LONLAT) -> List[Point]:
    """
    Returns the points in the linestring in the order
    which is given by the direction of the route.

    The points are returned in the projection system of the linestring.

    Source: https://github.com/priobike/priobike-sg-selector

    MIT License

    Copyright (c) 2023 PrioBike-HH

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
    """

    system_linestring = linestring.transform(system, clone=True)
    system_route = route.transform(system, clone=True)

    points = []
    fractions = []
    for coord in system_linestring.coords:
        point_geometry = Point(*coord, srid=system)
        points.append(point_geometry.transform(linestring.srid, clone=True))
        fraction = system_route.project_normalized(point_geometry)
        fractions.append(fraction)

    return [p for p, _ in sorted(zip(points, fractions), key=lambda x: x[1])]


def project_onto_route(
    linestring: LineString,
    route: LineString,
    use_route_direction=True,
    system=settings.METRICAL,
) -> LineString:
    """
    Projects a linestring onto a route linestring.

    Use the given projection system to perform the projection.
    If `use_route_direction` is True, the direction of the route is used.

    Source: https://github.com/priobike/priobike-sg-selector

    MIT License

    Copyright (c) 2023 PrioBike-HH

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
    """

    system_linestring = linestring.transform(system, clone=True)
    system_route = route.transform(system, clone=True)

    if use_route_direction:
        points = points_in_route_dir(system_linestring, system_route, system)
    else:
        points = [Point(*coord, srid=system)
                  for coord in system_linestring.coords]

    projected_points = []
    for point_geometry in points:
        # Get the fraction of the route that the point is closest to
        fraction = system_route.project_normalized(point_geometry)
        # Interpolate the point along the route
        projected_points.append(system_route.interpolate_normalized(fraction))

    # Project back to the original coordinate system
    projected_linestring = LineString(projected_points, srid=system)
    projected_linestring.transform(linestring.srid)
    return projected_linestring


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

    nearby_point_pois = Poi.objects.filter(category=type_of_poi, coordinate__dwithin=(route_linestring, D(m=threshold)))
    nearby_line_pois = PoiLine.objects.filter(category=type_of_poi, line__dwithin=(route_linestring, D(m=threshold)))

    if not nearby_point_pois and not nearby_line_pois:
        return []

    # Match each coordinate onto the route in the mercator projection
    route_lstr_mercator = route_linestring.transform(settings.METRICAL, clone=True)
    route_length_mercator = route_lstr_mercator.length
    segments = []
    for poi in nearby_point_pois:
        poi_coordinate_mercator = poi.coordinate.transform(settings.METRICAL, clone=True)
        dist_on_route = route_lstr_mercator.project(poi_coordinate_mercator)
        dist_start = max(0, dist_on_route - elongation)
        dist_end = min(route_length_mercator, dist_on_route + elongation)
        segments.append([dist_start, dist_end])
    for poi in nearby_line_pois:
        poi_line_mercator = poi.line.transform(settings.METRICAL, clone=True)
        projected_line = project_onto_route(poi_line_mercator, route_lstr_mercator)
        for i in range(len(projected_line.coords) - 1):
            dist_start = route_lstr_mercator.project(Point(projected_line.coords[i], srid=settings.METRICAL))
            dist_end = route_lstr_mercator.project(Point(projected_line.coords[i + 1], srid=settings.METRICAL))
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
