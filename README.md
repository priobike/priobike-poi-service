# POI Service

A microservice to receive and match POIs (Points of Interest) with routes.

## Quickstart

```bash
docker-compose up
```

## REST Endpoints


**TODO: Die ganzen Beispiel-Nachrichten auf POIs anpassen**


#### POST /poi/post/

```bash
curl --data "@example-poi.json" -X POST -H "Content-Type: application/json" http://localhost/production/poi-service/poi/post/
```
Result:
```json
{
    "success": true
}
```

#### POST /poi/match/

```bash
curl --data "@example-route.json" -X POST -H "Content-Type: application/json" http://localhost/production/poi-service/poi/match/
```
Result:
```json
{
    "success": true,
    "poi": [
        {
            "pk": 1,
            "category": "obstacle",
            "lon": 13.38886,
            "lat": 52.517037,
            "votes": 0,
            "date": "2023-01-18T13:24:07.545Z"
        }
    ]
}
```
