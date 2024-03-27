import json

from django.conf import settings
from django.contrib.gis.geos import LineString
from django.http import HttpResponseBadRequest, HttpResponseServerError, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from poi.models import Construction, ConstructionSpot, Recommendation


@method_decorator(csrf_exempt, name="dispatch")
class PostConstructionResource(View):
    def post(self, request):
        try:
            json_data = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid request."}))

        # Get query parameter "type"
        type = request.GET.get("type", "discomfort")

        if type == "recommendation":
            try:
                Recommendation.objects.create(
                    coordinate=f"POINT({json_data['lon']} {json_data['lat']})",
                    category=json_data["category"],
                )
            except KeyError:
                return HttpResponseBadRequest(json.dumps({"error": "Invalid request."}))
            except Exception:
                return HttpResponseServerError(
                    json.dumps({"error": "Internal server error."})
                )

            return JsonResponse({"success": True})

        try:
            Construction.objects.create(
                coordinate=f"POINT({json_data['lon']} {json_data['lat']})",
                category=json_data["category"],
            )
        except KeyError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid request."}))
        except Exception:
            return HttpResponseServerError(
                json.dumps({"error": "Internal server error."})
            )

        return JsonResponse({"success": True})


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

        try:
            construction_spots = ConstructionSpot.objects.filter(
                border__intersects=route_linestring
            ).filter(value__gte=0)
        except KeyError:
            return HttpResponseBadRequest(json.dumps({"error": "Invalid request."}))
        except Exception:
            return HttpResponseServerError("Internal server error.")

        construction_response = []
        for construction_spot in construction_spots:
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
