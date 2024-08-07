#!/bin/bash

# Normally, the docker container will need to process data when it is started.
# This will cause a lot of time and redundant comutational effort to be wasted.
# So, we can preheat the docker images to avoid this problem. This script is
# part of the Dockerfile, and will be executed when the docker image is built.

echo "Preheating the docker image..."

# Run postgres in the background
./run-postgres.sh

# Check if previous command failed. If it did, exit
ret=$?
if [ $ret -ne 0 ]; then
    echo "Failed to start postgres"
    exit $ret
fi

# Run the migration script
poetry run python backend/manage.py migrate

# Check if previous command failed. If it did, exit
ret=$?
if [ $ret -ne 0 ]; then
    echo "Migration failed"
    exit $ret
fi

poetry run python backend/manage.py import_constructions ${LOCATION}

# Check if previous command failed. If it did, exit
ret=$?
if [ $ret -ne 0 ]; then
    echo "Failed to load constructions data."
    exit $ret
fi

poetry run python backend/manage.py import_accident_hotspots ${LOCATION}

# Check if previous command failed. If it did, exit
ret=$?
if [ $ret -ne 0 ]; then
    echo "Failed to load accident hotspot data."
    exit $ret
fi

poetry run python backend/manage.py import_green_waves ${LOCATION}

# Check if previous command failed. If it did, exit
ret=$?
if [ $ret -ne 0 ]; then
    echo "Failed to load green wave data."
    exit $ret
fi

poetry run python backend/manage.py import_velo_routes ${LOCATION}

# Check if previous command failed. If it did, exit
ret=$?
if [ $ret -ne 0 ]; then
    echo "Failed to load velo routes data."
    exit $ret
fi

poetry run python backend/manage.py import_landmarks ${LOCATION}

# Check if previous command failed. If it did, exit
ret=$?
if [ $ret -ne 0 ]; then
    echo "Failed to load landmarks data."
    exit $ret
fi

echo "Timestamp:"
echo $(date)

echo "Preheating complete!"
