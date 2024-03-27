import json

from construction.models import Construction
from django.conf import settings
from django.contrib.gis.geos import LineString
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View


@method_decorator(csrf_exempt, name="dispatch")
class MatchConstructionResource(View):
    def post(self, request):
        try:
            json_data = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid request."}))
        route = json_data.get("route")
        if not route:
            return HttpResponseBadRequest(json.dumps({"error": "No route data"}))

        try:
            route_points = [(point["lon"], point["lat"]) for point in route]
        except KeyError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid route data"}))

        try:
            route_linestring = LineString(route_points, srid=settings.LONLAT)
        except ValueError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid route points"}))

        construction_response = []
        # Find all constructions that intersect with the route.
        for construction_spot in Construction.objects.all():
            intersections = construction_spot.border.intersection(route_linestring)
            if intersections.geom_type == "MultiLineString":
                for linestring in intersections:
                    construction_response.append(
                        {
                            "coordinates": [list(coord) for coord in linestring.coords],
                            "weight": construction_spot.value,
                        }
                    )
            elif intersections.geom_type == "LineString":
                construction_response.append(
                    {
                        "coordinates": [list(coord) for coord in intersections.coords],
                        "weight": construction_spot.value,
                    }
                )
            else:
                print("Unknown geometry type:", intersections.geom_type)

        return JsonResponse({"success": True, "constructions": construction_response})
