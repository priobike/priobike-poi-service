# POI Service

A microservice to receive and match POIs (Points of Interest) like construction sites with routes.

## Quickstart

```bash
docker-compose up
```

# Constructions
## REST Endpoints
#### POST /construction/match/

```bash
curl --data "@example-route.json" -X POST -H "Content-Type: application/json" http://localhost/production/poi-service/construction/match
```
Result (lon, lat):
```json
{
    "success": true,
    "constructions": [
        [10.025769050998635, 53.55364501850376],
        [9.91464352044119, 53.627661081124124]
    ]
}
```
