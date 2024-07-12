import json

import natsort

PATH = "/home/charly/Schreibtisch/PrioBike/priobike-poi-service/backend/pois/openstreetbrowser-osm-tags-de.json"

with open(PATH) as f:
    translation_table = json.load(f)

# Sort the tags by key
sorted_tags = natsort.natsorted(translation_table.keys())

# if value description is not available, set it to an empty string
for key in sorted_tags:
    if "description" not in translation_table[key]:
        translation_table[key]["description"] = ""

# save the sorted tags to a new file
with open(PATH, "w") as f:
    json.dump(translation_table, f, indent=4)
