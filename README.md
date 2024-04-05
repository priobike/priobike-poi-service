# POI Service

A microservice to receive and match POIs (Points of Interest) like construction sites with routes.

## Quickstart

```bash
docker-compose up
```

# Constructions
## REST Endpoints
#### POST /construction/match/

Returns segments along the given route that have constructions.
Parameters: 

`elongation` - How much the found construction coordinates should be elongated along the route.
`threshold` - The distance threshold for matching.

```bash
curl --data "@example-route.json" -X POST -H "Content-Type: application/json" http://localhost:8000/construction/match
```
Result (lon, lat):
```json
{
    "success":true,
    "constructions":[
        [
            [
                9.977496000000002,
                53.56414999999999
            ],
            [
                9.977496000000002,
                53.56414999999999
            ],
            [
                9.977694,
                53.564157
            ],
            [
                9.977958627965451,
                53.56414820272196
            ]
        ],
        [
            [
                9.988102652319556,
                53.56217294016667
            ],
            [
                9.988813282899391,
                53.561801544837
            ]
        ],
        [
            [
                9.98990412256171,
                53.561168318642814
            ],
            [
                9.99005,
                53.56103999999999
            ],
            [
                9.989899,
                53.56097299999999
            ],
            [
                9.989899,
                53.56097299999999
            ],
            [
                9.990058999999999,
                53.560790999999995
            ],
            [
                9.990058999999999,
                53.560790999999995
            ]
        ]
    ]
}
```

`NOTE` For demo purposes, this uses a threshold of 500m contained in the request JSON. The app should use a much smaller threshold.
