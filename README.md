# priobike-poi-service

A Django service that matches points of interests such as construction sites along given (bike) routes. Using this service, it is possible to display segments along the route which may represent an obstacle or are otherwise of interest during route planning.

The data is mainly fetched from an overpass API such as https://overpass-turbo.eu/ or also a self-hosted instance, as with our [custom overpass](https://github.com/priobike/priobike-overpass) based on the [DRN bike routing dataset for Hamburg](https://github.com/priobike/priobike-graphhopper-drn).

The PrioBike app uses this service to display warning signs and other useful information in the routing view.

[Learn more about PrioBike](https://github.com/priobike)

## Quickstart

The recommended way to spin up a minimal setup of this service is to use the docker-compose setup:

```bash
docker-compose up
```

## CLI

See [here](https://github.com/priobike/priobike-poi-service/tree/main/backend/pois/management/commands) for available POI management commands to load POIs into the database and [here](https://docs.djangoproject.com/en/5.0/ref/django-admin/) for further information on how they are used. The [`run-preheating.sh`](https://github.com/priobike/priobike-poi-service/blob/main/run-preheating.sh) script gives you some examples.

## API

### POST /pois/match/

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

`NOTE` For demo purposes, this uses a threshold of 500m contained in the request JSON. Normally you would define a lower threshold to not fetch very distant POIs.

## What else to know

During the build of this service, it performs a preheating to load and fill the Postgres database with points of interest. The Postgres database runs as a background process of the Docker container.

## Contributing

We highly encourage you to open an issue or a pull request. You can also use our repository freely with the `MIT` license. 

Every service runs through testing before it is deployed in our release setup. Read more in our [PrioBike deployment readme](https://github.com/priobike/.github/blob/main/wiki/deployment.md) to understand how specific branches/tags are deployed.

## Anything unclear?

Help us improve this documentation. If you have any problems or unclarities, feel free to open an issue.
