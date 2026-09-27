#!/bin/sh
# First-start initialisation for the Postgres container (docker-compose.yml
# mounts this into /docker-entrypoint-initdb.d/). Applies the schema files,
# then the reference seed data the warehouse's foreign keys depend on — so a
# fresh clone needs no psql client or `make migrate` on the host.
# Runs only when the data volume is empty; `docker compose down -v` resets it.
set -eu

for f in /database/schema/*.sql /database/seed/*.sql; do
    echo "applying $f"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$f"
done
