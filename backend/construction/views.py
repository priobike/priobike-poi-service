import json

from construction.models import Construction
from django.conf import settings
from django.contrib.gis.geos import LineString
from django.contrib.gis.measure import D
from django.http import HttpResponseBadRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View


@method_decorator(csrf_exempt, name="dispatch")
class MatchConstructionResource(View):
    def post(self, request):
        print("Received post request: " + str(request.body))

        try:
            json_data = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid request."}))
        print("Received JSON data: " + str(json_data))

        route = json_data.get("route")
        if not route:
            return HttpResponseBadRequest(json.dumps({"error": "No route data"}))
        print("Received route data: " + str(route))

        try:
            route_points = [(point["lon"], point["lat"]) for point in route]
        except KeyError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid route data"}))
        print("Received route points: " + str(route_points))

        try:
            route_linestring: LineString = LineString(
                route_points, srid=settings.LONLAT
            )
        except ValueError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid route points"}))
        print("Received route linestring: " + str(route_linestring))

        print(
            f"Checking all {Construction.objects.count()} construction sites for proximity to route."
        )

        DISTANCE_THRESHOLD = 50  # meters
        relevant_constructions = Construction.objects.filter(
            coordinate__dwithin=(route_linestring, D(m=DISTANCE_THRESHOLD))
        )
        print(f"Found {relevant_constructions.count()} relevant construction sites.")

        json_body = {
            "success": True,
            "constructions": [
                [construction.coordinate.x, construction.coordinate.y]
                for construction in relevant_constructions
            ],
        }

        return JsonResponse(json_body)
