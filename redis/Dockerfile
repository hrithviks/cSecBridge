# Use an official Redis image as a parent image
FROM redis:7.2-alpine

# Copy Redis configuration file into the container
COPY redis.conf /usr/local/etc/redis/redis.conf

# Copy the ACL template file into the image.
COPY users.acl.tpl /usr/local/etc/redis/users.acl.tpl

# Copy the entrypoint script into the image's execution path and make it executable
COPY docker-entrypoint.sh /usr/local/bin/

RUN apk add --no-cache su-exec \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && chown redis:redis /data \
    && chown redis:redis /usr/local/etc/redis/redis.conf

# Set the entrypoint to the custom script
ENTRYPOINT ["docker-entrypoint.sh"]

# Set the default command to run. This command is passed as arguments to the
# entrypoint script. It uses the custom configuration file.
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]
