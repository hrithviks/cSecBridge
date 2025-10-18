# Use the official PostgreSQL 15 image based on Alpine Linux
FROM postgres:15-alpine

# Automatic Database Init
COPY init.sql /docker-entrypoint-initdb.d/

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB || exit 1
