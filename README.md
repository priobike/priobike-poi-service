# POI Service

A microservice to receive and match POIs (Points of Interest) like construction sites with routes.

## Quickstart

```bash
docker-compose up
```

# Pois
## REST Endpoints
#### POST /pois/match/

Returns segments along the given route that have pois.
Parameters: 

`elongation` - How much the found pois coordinates should be elongated along the route.
`threshold` - The distance threshold for matching.

```bash
curl --data "@example-route.json" -X POST -H "Content-Type: application/json" http://localhost:8000/pois/match
```
Result (lon, lat):
```json
{"success": true, "constructions": [[[9.977496000000002, 53.564149999999984], [9.977694, 53.56415699999998], [9.977496000000002, 53.564149999999984], [9.977694, 53.56415699999998], [9.977694, 53.56415699999998], [9.977958627965453, 53.56414820272195]], [[9.98810265231947, 53.56217294016669], [9.988394, 53.56202399999999], [9.988394, 53.56202399999999], [9.988813282899335, 53.56180154483703]], [[9.9899041225617, 53.561168318642814], [9.99005, 53.56103999999997], [9.99005, 53.56103999999997], [9.989899, 53.56097299999999], [9.989899, 53.56097299999999], [9.990058999999999, 53.56079099999999], [9.989899, 53.56097299999999], [9.990058999999999, 53.56079099999999]]], "accidenthotspots": [[[9.989981906465397, 53.561009786325585], [9.989899, 53.56097299999999], [9.989899, 53.56097299999999], [9.990058999999999, 53.56079099999999], [9.989899, 53.56097299999999], [9.990058999999999, 53.56079099999999]]], "greenwaves": [], "veloroutes": [[[9.989981906465397, 53.561009786325585], [9.989899, 53.56097299999999], [9.989899, 53.56097299999999], [9.990058999999999, 53.56079099999999], [9.989899, 53.56097299999999], [9.990058999999999, 53.56079099999999]]]}
```

`NOTE` For demo purposes, this uses a threshold of 500m contained in the request JSON. The app should use a much smaller threshold.
