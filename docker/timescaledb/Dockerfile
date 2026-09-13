# REGENOVA TimescaleDB — Dockerfile
FROM timescale/timescaledb:latest-pg16

# Copy initialization SQL scripts
COPY docker/timescaledb/init/ /docker-entrypoint-initdb.d/

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
  CMD pg_isready -U ${POSTGRES_USER:-regenova_timeseries_db} -d ${POSTGRES_DB:-regenova_timeseries_db} || exit 1
