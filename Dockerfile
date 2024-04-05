ARG ENVIRONMENT=release

FROM postgis/postgis:14-3.3 AS builder
# This docker image is based on the bullseye operating system
# See: https://github.com/postgis/docker-postgis/blob/master/14-3.3/Dockerfile

# Install libraries needed for GeoDjango and PostGIS
# See https://docs.djangoproject.com/en/3.2/ref/contrib/gis/install/geolibs/
RUN apt-get update && apt-get install -y \
  binutils \
  libproj-dev \
  gdal-bin

# Install Postgres client to check liveness of the database
RUN apt-get install -y postgresql-client

# Install osm2pgsql to load the osm-data into the database
RUN apt-get install -y osm2pgsql

# Install Python and a dependency for psycopg2
RUN apt-get install -y python3 python3-pip libpq-dev

# Install Poetry as the package manager for this application
RUN pip install poetry

WORKDIR /code

# Install Python dependencies separated from the
# run script to enable Docker caching
ADD pyproject.toml /code
# Install all dependencies
RUN poetry install

# Install CURL for healthcheck
RUN apt-get update && apt-get install -y curl

# Expose Django port, DO NOT EXPOSE THE DATABASE PORT!
EXPOSE 8000

COPY . /code

# Used for preheating the correct POIs from overpass turbo.
ARG LOCATION=Hamburg
ENV LOCATION=${LOCATION}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENV POSTGRES_NAME=poiservice-db
ENV POSTGRES_USER=poiservice-user
ENV POSTGRES_PASSWORD=poiservice-password
ENV POSTGRES_DB=poiservice-db
ENV POSTGRES_HOST=localhost
ENV POSTGRES_PORT=5432

ENV HEALTHCHECK_TOKEN=healthcheck-token

# Use this argument to invalidate the cache of subsequent steps.
ARG CACHE_DATE=1970-01-01

FROM builder AS test
# Only run postgres to execute tests
CMD "./run-test.sh"

FROM builder AS dev
ENV DJANGO_DEBUG_MODE=True
# Run the development server
RUN ./run-preheating.sh
HEALTHCHECK --interval=60s --timeout=10s --retries=5 --start-period=10s \
  CMD curl --fail http://localhost:8000/healthcheck?token=healthcheck-token || exit 1
CMD "./run-dev.sh"

FROM builder AS production
ENV DJANGO_DEBUG_MODE=False
# Preheat our database, by running migrations and pre-loading data
RUN ./run-preheating.sh
HEALTHCHECK --interval=60s --timeout=10s --retries=5 --start-period=10s \
  CMD curl --fail http://localhost:8000/healthcheck?token=healthcheck-token || exit 1
CMD "./run-prod.sh"
