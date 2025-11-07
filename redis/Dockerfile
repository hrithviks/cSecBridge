# Use the official Redis image based on Alpine Linux
FROM redis:7-alpine

# Copy Redis configuration file into the container
COPY redis.conf /usr/local/etc/redis/redis.conf

# Update ownership for the configuration file
RUN chown redis:redis /usr/local/etc/redis/redis.conf

# Healthcheck configuration
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD redis-cli -a "$REDIS_PASSWORD" ping || exit 1

# Entrypoint for the container
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
