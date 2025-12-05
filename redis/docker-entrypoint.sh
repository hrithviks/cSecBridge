#!/bin/sh
# Exit immediately if a command exits with a non-zero status.
set -e

# Define the path for the ACL template and the final ACL file
ACL_TEMPLATE="/usr/local/etc/redis/users.acl.tpl"
ACL_FILE="/data/users.acl" # Should match with the entry in redis.conf

# Define the path for the Redis configuration file
CONF_FILE="/usr/local/etc/redis/redis.conf"

# Check if the required environment variable from Terraform is set
if [ -z "$REDIS_ADMIN_PASSWORD" ]; then
  echo "Error: One or more required environment variables (REDIS_ADMIN_PASSWORD, REDIS_CSB_API_USER, REDIS_CSB_API_PASSWORD) are not set." >&2
  exit 1
fi

# Helper function to escape special characters for sed.
# This handles '&', '\', and the sed delimiter '/'.
escape_for_sed() {
  echo "$1" | sed -e 's/[&/\\]/\\&/g'
}

# Escape the passwords to make them safe for sed.
SAFE_ADMIN_PASSWORD=$(escape_for_sed "$REDIS_ADMIN_PASSWORD")
#SAFE_CSB_API_PASSWORD=$(escape_for_sed "$REDIS_CSB_API_PASSWORD")

# Generate file users.acl
echo "Generating Redis ACL file from template..."
# Use the escaped passwords in the sed command.
sed -e "s/\${admin_password}/${SAFE_ADMIN_PASSWORD}/g" "$ACL_TEMPLATE" > "$ACL_FILE"

# Update redis.conf with the admin password
echo "Setting admin password in redis.conf..."

# Use a temporary file for sed.
TMP_CONF_FILE=$(mktemp)

# Comment out requirepass in redis.conf
sed "s/requirepass password-placeholder/# requirepass is handled by the aclfile/g" "$CONF_FILE" > "$TMP_CONF_FILE"
mv "$TMP_CONF_FILE" "$CONF_FILE"

# Set file ownership to redis
chown redis:redis "$ACL_FILE" "$CONF_FILE"

# The redis-server command is passed as arguments ("$@") to this script.
echo "Configuration complete. Starting Redis server..."

# Switch to the 'redis' user and execute the CMD from the Dockerfile.
exec su-exec redis "$@"
